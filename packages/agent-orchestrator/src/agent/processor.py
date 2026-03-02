"""Article processing pipeline for the Agent Orchestrator.

Processes raw article lists through:
1. Deduplication (by URL)
2. Clustering (LLM-based topic grouping)
3. Signal extraction
4. Risk identification
5. Opportunity detection
6. Action item generation
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from anthropic import AsyncAnthropic

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

_FAST_MODEL = "claude-haiku-4-5-20251001"  # for intermediate processing steps


def _extract_json(text: str) -> str:
    """Strip markdown code fences before JSON parsing."""
    text = re.sub(r"```(?:json)?\s*\n?", "", text)
    text = text.replace("```", "")
    return text.strip()


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

CLUSTERING_PROMPT = """You are a competitive intelligence analyst. Given a list of news article titles and snippets,
group them into thematic clusters. Return ONLY valid JSON — no preamble, no markdown.

Output format:
{
  "clusters": [
    {
      "theme": "<concise theme name, max 6 words>",
      "article_indices": [<0-based indices of articles in this cluster>]
    }
  ]
}

Rules:
- Create 2-6 clusters maximum
- Every article must belong to exactly one cluster
- Use business-meaningful themes (e.g., "Ad Platform Updates", "Partnership Announcements", "Pricing Changes")
- If there are fewer than 3 articles, create one cluster called "General News"

Articles:
{articles_json}"""

SIGNAL_EXTRACTION_PROMPT = """You are a competitive intelligence analyst. Given a theme and a set of article titles
and snippets grouped under that theme, extract the single most important business signal.

Return ONLY valid JSON — no preamble, no markdown.

Output format:
{
  "signal": "<1-2 sentence business-impact summary of what happened and why it matters>",
  "relevance": "<high|medium|low>",
  "best_article_index": <0-based index of the most relevant article in this cluster>
}

Rules:
- The signal MUST be directly supported by the article content — no extrapolation
- relevance = high if this affects competitive positioning directly
- relevance = medium if it provides useful context
- relevance = low if it is tangentially related

Theme: {theme}
Articles:
{articles_json}"""

RISK_OPPORTUNITY_PROMPT = """You are a competitive intelligence analyst. Given a list of article signals,
identify competitive risks and strategic opportunities.

Return ONLY valid JSON — no preamble, no markdown.

Output format:
{
  "risks": [
    {
      "description": "<1-2 sentence risk description>",
      "severity": "<high|medium|low>",
      "signal_indices": [<0-based indices of signals that support this risk>]
    }
  ],
  "opportunities": [
    {
      "description": "<1-2 sentence opportunity description>",
      "confidence": "<high|medium|low>",
      "signal_indices": [<0-based indices of signals that support this opportunity>]
    }
  ]
}

Rules:
- Only include risks/opportunities that are DIRECTLY supported by the provided signals
- If no risks are evident, return an empty risks array
- If no opportunities are evident, return an empty opportunities array
- Maximum 5 risks and 5 opportunities
- Descriptions must reference specific facts from the signals, not generic statements

Signals:
{signals_json}"""

ACTION_ITEM_PROMPT = """You are a competitive intelligence analyst. Given a list of risks and opportunities,
generate a prioritized list of action items for an operations team.

Return ONLY valid JSON — no preamble, no markdown.

Output format:
{
  "action_items": [
    {
      "action": "<specific, actionable step — start with a verb>",
      "priority": "<P0|P1|P2>",
      "rationale": "<1 sentence explaining why this action and priority>"
    }
  ]
}

Priority definitions:
- P0: Act now (today) — addresses an immediate competitive threat
- P1: This week — addresses a developing situation
- P2: Track — monitor but no immediate action needed

Rules:
- Maximum 8 action items
- Every action must reference a specific risk or opportunity
- Actions must be concrete and role-appropriate for RevOps, Marketing Ops, or Product Ops teams
- If there are no risks or opportunities, return an empty action_items array

Risks:
{risks_json}

Opportunities:
{opportunities_json}"""


# ---------------------------------------------------------------------------
# Public pipeline functions
# ---------------------------------------------------------------------------


def deduplicate_articles(articles: list[Article]) -> list[Article]:
    """Remove duplicate articles by URL, preserving first occurrence order.

    Args:
        articles: Raw list of articles from all tool calls (may contain duplicates).

    Returns:
        Deduplicated list of articles.
    """
    seen_urls: set[str] = set()
    unique: list[Article] = []
    for article in articles:
        if article.url and article.url not in seen_urls:
            seen_urls.add(article.url)
            unique.append(article)
    logger.info("Deduplicated: %d → %d articles", len(articles), len(unique))
    return unique


async def cluster_articles(articles: list[Article]) -> list[ArticleCluster]:
    """Group articles into thematic clusters using LLM classification.

    Args:
        articles: Deduplicated list of articles to cluster.

    Returns:
        List of ArticleCluster objects, each with a theme and article list.
    """
    if not articles:
        return []

    # If very few articles, skip clustering
    if len(articles) <= 2:
        return [ArticleCluster(theme="General News", articles=articles)]

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Build a compact representation of articles for the prompt
    articles_data = [
        {"index": i, "title": a.title, "snippet": a.snippet[:200], "source": a.source}
        for i, a in enumerate(articles)
    ]
    articles_json = json.dumps(articles_data, indent=2)

    prompt = CLUSTERING_PROMPT.replace("{articles_json}", articles_json)

    message = await client.messages.create(
        model=_FAST_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
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

    # Any articles not assigned to a cluster go into "Other"
    unassigned = [a for i, a in enumerate(articles) if i not in used_indices]
    if unassigned:
        clusters.append(ArticleCluster(theme="Other", articles=unassigned))

    logger.info("Clustered %d articles into %d themes", len(articles), len(clusters))
    return clusters


async def _extract_signal_for_cluster(
    client: AsyncAnthropic, cluster: ArticleCluster
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
        message = await client.messages.create(
            model=_FAST_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
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
    """Extract the key business signal from each article cluster.

    All clusters are processed concurrently via asyncio.gather().

    Args:
        clusters: List of article clusters with themes.

    Returns:
        List of KeySignal objects, one per cluster (or fewer if extraction fails).
    """
    if not clusters:
        return []

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    tasks = [_extract_signal_for_cluster(client, cluster) for cluster in clusters]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    signals: list[KeySignal] = []
    for r in results:
        if isinstance(r, KeySignal):
            signals.append(r)
        elif isinstance(r, Exception):
            logger.warning("Signal extraction task raised an exception: %s", r)

    # Sort by relevance: high > medium > low
    relevance_order = {"high": 0, "medium": 1, "low": 2}
    signals.sort(key=lambda s: relevance_order.get(s.relevance, 1))
    logger.info("Extracted %d signals from %d clusters", len(signals), len(clusters))
    return signals


async def identify_risks_and_opportunities(
    signals: list[KeySignal],
    all_articles: list[Article],
) -> tuple[list[Risk], list[Opportunity]]:
    """Identify competitive risks and strategic opportunities from extracted signals.

    Args:
        signals: List of extracted key signals.
        all_articles: All deduplicated articles (for source URL resolution).

    Returns:
        Tuple of (risks, opportunities).
    """
    if not signals:
        return [], []

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Build a URL index for quick source lookup
    url_by_title: dict[str, str] = {a.title: a.url for a in all_articles}

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
    prompt = RISK_OPPORTUNITY_PROMPT.replace("{signals_json}", signals_json)

    try:
        message = await client.messages.create(
            model=_FAST_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        parsed = json.loads(_extract_json(raw))
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Failed to identify risks/opportunities: %s", exc)
        return [], []

    # Build risks
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

    # Build opportunities
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
) -> list[ActionItem]:
    """Synthesize prioritized action items from risks and opportunities.

    Args:
        risks: Identified competitive risks.
        opportunities: Identified strategic opportunities.

    Returns:
        Ordered list of ActionItem objects sorted by priority.
    """
    if not risks and not opportunities:
        return []

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    risks_data = [
        {"index": i, "description": r.description, "severity": r.severity}
        for i, r in enumerate(risks)
    ]
    opps_data = [
        {"index": i, "description": o.description, "confidence": o.confidence}
        for i, o in enumerate(opportunities)
    ]
    prompt = ACTION_ITEM_PROMPT.replace("{risks_json}", json.dumps(risks_data, indent=2)).replace("{opportunities_json}", json.dumps(opps_data, indent=2))

    try:
        message = await client.messages.create(
            model=_FAST_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
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

    # Sort by priority
    action_items.sort(key=lambda a: priority_order.get(a.priority, 2))
    logger.info("Generated %d action items", len(action_items))
    return action_items
