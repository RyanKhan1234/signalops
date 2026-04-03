"""Article processing pipeline for the Agent Orchestrator.

All LLM calls go through LangChain's ChatOpenAI for consistent model
abstraction. Processes raw article lists through:
1. Deduplication (by URL)
2. Clustering (LLM-based topic grouping)
3. Key finding extraction
4. Concern identification
5. Interesting angle detection
6. Next step generation
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from src.config import settings
from src.models.digest import (
    ActionItem,
    Article,
    ArticleCluster,
    KeySignal,
    Opportunity,
    Risk,
)

logger = logging.getLogger(__name__)


def _get_llm() -> ChatOpenAI:
    """Get a LangChain ChatOpenAI instance for processing steps."""
    return ChatOpenAI(
        model=settings.research_model,
        api_key=settings.openai_api_key,
        temperature=0.1,
    )


def _extract_json(text: str) -> str:
    """Strip markdown code fences before JSON parsing."""
    text = re.sub(r"```(?:json)?\s*\n?", "", text)
    text = text.replace("```", "")
    return text.strip()


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

CLUSTERING_PROMPT = """Given a list of article titles and snippets, group them into thematic clusters.
Return ONLY valid JSON — no preamble, no markdown.

Output format:
{{
  "clusters": [
    {{
      "theme": "<concise theme name, max 6 words>",
      "article_indices": [<0-based indices of articles in this cluster>]
    }}
  ]
}}

Rules:
- Create 2-6 clusters maximum
- Every article must belong to exactly one cluster
- Use descriptive themes based on what the articles are actually about
- If there are fewer than 3 articles, create one cluster called "General"

Articles:
{articles_json}"""

SIGNAL_EXTRACTION_PROMPT = """Given a theme and a set of article titles and snippets, extract the
single most important finding or development.

Return ONLY valid JSON — no preamble, no markdown.

Output format:
{{
  "signal": "<1-2 sentence summary of what happened and why it's interesting>",
  "relevance": "<high|medium|low>",
  "best_article_index": <0-based index of the most relevant article in this cluster>
}}

Rules:
- The finding MUST be directly supported by the article content — no extrapolation
- relevance = high if this is a significant development you'd want to know about
- relevance = medium if it provides useful context or background
- relevance = low if it is tangentially related

Theme: {theme}
Articles:
{articles_json}"""

RISK_OPPORTUNITY_PROMPT = """Given the findings below, identify things to watch out for and
interesting angles worth exploring further.

Return ONLY valid JSON — no preamble, no markdown.

Output format:
{{
  "risks": [
    {{
      "description": "<1-2 sentence description of what to watch out for>",
      "severity": "<high|medium|low>",
      "signal_indices": [<0-based indices of findings that support this>]
    }}
  ],
  "opportunities": [
    {{
      "description": "<1-2 sentence description of an interesting thread to pull on>",
      "confidence": "<high|medium|low>",
      "signal_indices": [<0-based indices of findings that support this>]
    }}
  ]
}}

Rules:
- Only include items DIRECTLY supported by the provided findings
- If nothing concerning stands out, return an empty risks array
- If no interesting angles, return an empty opportunities array
- Maximum 5 of each
- Be specific — reference actual facts from the findings, not generic observations

Findings:
{signals_json}"""

ACTION_ITEM_PROMPT = """Given the concerns and interesting angles below, suggest concrete next steps
for someone researching this topic.

Return ONLY valid JSON — no preamble, no markdown.

Output format:
{{
  "action_items": [
    {{
      "action": "<specific, actionable step — start with a verb>",
      "priority": "<P0|P1|P2>",
      "rationale": "<1 sentence explaining why>"
    }}
  ]
}}

Priority definitions:
- P0: Dig into this now — time-sensitive or particularly important
- P1: Get to this week — developing situation worth following up on
- P2: Bookmark for later — worth tracking but not urgent

Rules:
- Maximum 8 items
- Every item must reference a specific concern or angle from the input
- Think practically — what would someone actually do with this information?
- If there's nothing actionable, return an empty action_items array

Concerns:
{risks_json}

Interesting angles:
{opportunities_json}"""


# ---------------------------------------------------------------------------
# Public pipeline functions
# ---------------------------------------------------------------------------


def deduplicate_articles(articles: list[Article]) -> list[Article]:
    """Remove duplicate articles by URL, preserving first occurrence order."""
    seen_urls: set[str] = set()
    unique: list[Article] = []
    for article in articles:
        if article.url and article.url not in seen_urls:
            seen_urls.add(article.url)
            unique.append(article)
    logger.info("Deduplicated: %d → %d articles", len(articles), len(unique))
    return unique


async def cluster_articles(articles: list[Article]) -> list[ArticleCluster]:
    """Group articles into thematic clusters using LLM classification."""
    if not articles:
        return []

    if len(articles) <= 2:
        return [ArticleCluster(theme="General News", articles=articles)]

    llm = _get_llm()

    articles_data = [
        {"index": i, "title": a.title, "snippet": a.snippet[:200], "source": a.source}
        for i, a in enumerate(articles)
    ]
    articles_json = json.dumps(articles_data, indent=2)
    prompt = CLUSTERING_PROMPT.replace("{articles_json}", articles_json)

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    raw = response.content.strip() if isinstance(response.content, str) else str(response.content)
    logger.debug("Clustering response: %s", raw[:500])

    try:
        parsed = json.loads(_extract_json(raw))
        clusters_data = parsed.get("clusters", [])
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("Failed to parse clustering response: %s — using single cluster", exc)
        return [ArticleCluster(theme="General News", articles=articles)]

    clusters: list[ArticleCluster] = []
    used_indices: set[int] = set()

    for cluster_data in clusters_data:
        indices = cluster_data.get("article_indices", [])
        theme = cluster_data.get("theme", "Uncategorized")
        cluster_articles: list[Article] = []
        for idx in indices:
            if isinstance(idx, int) and 0 <= idx < len(articles):
                cluster_articles.append(articles[idx])
                used_indices.add(idx)
        if cluster_articles:
            clusters.append(ArticleCluster(theme=theme, articles=cluster_articles))

    unassigned = [a for i, a in enumerate(articles) if i not in used_indices]
    if unassigned:
        clusters.append(ArticleCluster(theme="Other", articles=unassigned))

    logger.info("Clustered %d articles into %d themes", len(articles), len(clusters))
    return clusters


async def _extract_signal_for_cluster(
    llm: ChatOpenAI, cluster: ArticleCluster
) -> KeySignal | None:
    """Extract signal for a single cluster. Returns None on failure."""
    if not cluster.articles:
        return None

    articles_data = [
        {"index": i, "title": a.title, "snippet": a.snippet[:300], "url": a.url}
        for i, a in enumerate(cluster.articles)
    ]
    articles_json = json.dumps(articles_data, indent=2)
    prompt = SIGNAL_EXTRACTION_PROMPT.replace("{theme}", cluster.theme).replace(
        "{articles_json}", articles_json
    )

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content.strip() if isinstance(response.content, str) else str(response.content)
        parsed = json.loads(_extract_json(raw))

        best_idx = parsed.get("best_article_index", 0)
        if not isinstance(best_idx, int) or best_idx < 0 or best_idx >= len(cluster.articles):
            best_idx = 0

        best_article = cluster.articles[best_idx]
        signal_text = parsed.get("signal", "")
        relevance = parsed.get("relevance", "medium")
        if relevance not in ("high", "medium", "low"):
            relevance = "medium"

        if signal_text:
            return KeySignal(
                signal=signal_text,
                source_url=best_article.url,
                source_title=best_article.title,
                published_date=best_article.published_date,
                relevance=relevance,  # type: ignore[arg-type]
            )
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.warning("Failed to extract signal for cluster '%s': %s", cluster.theme, exc)

    return None


async def extract_signals(clusters: list[ArticleCluster]) -> list[KeySignal]:
    """Extract the key business signal from each article cluster."""
    if not clusters:
        return []

    llm = _get_llm()

    tasks = [_extract_signal_for_cluster(llm, cluster) for cluster in clusters]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    signals: list[KeySignal] = []
    for r in results:
        if isinstance(r, KeySignal):
            signals.append(r)
        elif isinstance(r, Exception):
            logger.warning("Signal extraction task raised an exception: %s", r)

    relevance_order = {"high": 0, "medium": 1, "low": 2}
    signals.sort(key=lambda s: relevance_order.get(s.relevance, 1))
    logger.info("Extracted %d signals from %d clusters", len(signals), len(clusters))
    return signals


async def identify_risks_and_opportunities(
    signals: list[KeySignal],
    all_articles: list[Article],
    user_context: str = "",
) -> tuple[list[Risk], list[Opportunity]]:
    """Identify risks, concerns, and opportunities from extracted signals."""
    if not signals:
        return [], []

    llm = _get_llm()

    signals_data = [
        {
            "index": i,
            "signal": s.signal,
            "source_url": s.source_url,
            "relevance": s.relevance,
        }
        for i, s in enumerate(signals)
    ]
    signals_json = json.dumps(signals_data, indent=2)
    context_prefix = ""
    if user_context.strip():
        context_prefix = (
            f"The person reading this research:\n{user_context.strip()}\n\n"
            f"Keep this in mind when deciding what matters to them.\n\n"
        )
    prompt = context_prefix + RISK_OPPORTUNITY_PROMPT.replace("{signals_json}", signals_json)

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content.strip() if isinstance(response.content, str) else str(response.content)
        parsed = json.loads(_extract_json(raw))
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Failed to identify risks/opportunities: %s", exc)
        return [], []

    risks: list[Risk] = []
    for r in parsed.get("risks", []):
        indices = r.get("signal_indices", [])
        source_urls = [
            signals[i].source_url
            for i in indices
            if isinstance(i, int) and 0 <= i < len(signals)
        ]
        if not source_urls and signals:
            source_urls = [signals[0].source_url]
        severity = r.get("severity", "medium")
        if severity not in ("high", "medium", "low"):
            severity = "medium"
        description = r.get("description", "")
        if description and source_urls:
            risks.append(
                Risk(
                    description=description,
                    severity=severity,  # type: ignore[arg-type]
                    source_urls=source_urls,
                )
            )

    opportunities: list[Opportunity] = []
    for o in parsed.get("opportunities", []):
        indices = o.get("signal_indices", [])
        source_urls = [
            signals[i].source_url
            for i in indices
            if isinstance(i, int) and 0 <= i < len(signals)
        ]
        if not source_urls and signals:
            source_urls = [signals[0].source_url]
        confidence = o.get("confidence", "medium")
        if confidence not in ("high", "medium", "low"):
            confidence = "medium"
        description = o.get("description", "")
        if description and source_urls:
            opportunities.append(
                Opportunity(
                    description=description,
                    confidence=confidence,  # type: ignore[arg-type]
                    source_urls=source_urls,
                )
            )

    logger.info(
        "Identified %d risks and %d opportunities", len(risks), len(opportunities)
    )
    return risks, opportunities


async def generate_action_items(
    risks: list[Risk],
    opportunities: list[Opportunity],
    user_context: str = "",
) -> list[ActionItem]:
    """Synthesize prioritized action items from risks and opportunities."""
    if not risks and not opportunities:
        return []

    llm = _get_llm()

    risks_data = [
        {"index": i, "description": r.description, "severity": r.severity}
        for i, r in enumerate(risks)
    ]
    opps_data = [
        {"index": i, "description": o.description, "confidence": o.confidence}
        for i, o in enumerate(opportunities)
    ]
    context_prefix = ""
    if user_context.strip():
        context_prefix = (
            f"The person reading this research:\n{user_context.strip()}\n\n"
            f"Suggest next steps that make sense for them specifically.\n\n"
        )
    prompt = context_prefix + ACTION_ITEM_PROMPT.replace("{risks_json}", json.dumps(risks_data, indent=2)).replace("{opportunities_json}", json.dumps(opps_data, indent=2))

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content.strip() if isinstance(response.content, str) else str(response.content)
        parsed = json.loads(_extract_json(raw))
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Failed to generate action items: %s", exc)
        return []

    action_items: list[ActionItem] = []
    priority_order = {"P0": 0, "P1": 1, "P2": 2}

    for item in parsed.get("action_items", []):
        action = item.get("action", "")
        priority = item.get("priority", "P2")
        rationale = item.get("rationale", "")
        if priority not in ("P0", "P1", "P2"):
            priority = "P2"
        if action:
            action_items.append(
                ActionItem(
                    action=action,
                    priority=priority,  # type: ignore[arg-type]
                    rationale=rationale,
                )
            )

    action_items.sort(key=lambda a: priority_order.get(a.priority, 2))
    logger.info("Generated %d action items", len(action_items))
    return action_items
