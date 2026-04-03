"""Digest composer for the Agent Orchestrator.

Assembles the final structured DigestResponse from processed article data.
Generates the executive summary and ensures all source references are populated.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from src.config import settings
from src.models.digest import (
    ActionItem,
    Article,
    DetectedIntent,
    DigestResponse,
    KeySignal,
    Opportunity,
    Risk,
    Source,
)
from src.models.trace import ToolTraceEntry

logger = logging.getLogger(__name__)

# Outlets considered high-credibility for risk scoring.
# Matched case-insensitively against the article's `source` field.
_HIGH_CREDIBILITY_OUTLETS: frozenset[str] = frozenset({
    "reuters",
    "bloomberg",
    "associated press",
    "ap news",
    "bbc",
    "bbc news",
    "the new york times",
    "new york times",
    "the wall street journal",
    "wall street journal",
    "wsj",
    "financial times",
    "the guardian",
    "washington post",
    "the washington post",
    "techcrunch",
    "the verge",
    "wired",
    "ars technica",
    "mit technology review",
    "nature",
    "science",
    "axios",
    "politico",
})


def _score_source_credibility(
    source_urls: list[str],
    url_to_article: dict[str, Article],
) -> Literal["high", "medium", "low"]:
    """Score how credible the sources backing a risk are.

    Rules:
    - high: any source is a recognized outlet, OR 3+ distinct outlets
    - medium: exactly 2 distinct outlets
    - low: single outlet not in the recognized list
    """
    outlets: list[str] = []
    for url in source_urls:
        article = url_to_article.get(url)
        if article and article.source:
            outlets.append(article.source.lower().strip())

    distinct_outlets = set(outlets)

    if any(o in _HIGH_CREDIBILITY_OUTLETS for o in distinct_outlets):
        return "high"
    if len(distinct_outlets) >= 3:
        return "high"
    if len(distinct_outlets) == 2:
        return "medium"
    return "low"


EXEC_SUMMARY_PROMPT = """Write a concise 2-3 sentence overview of what was found for this research query.
Write in a direct, conversational tone — like you're briefing a friend, not writing a report.

Rules:
- Maximum 3 sentences
- Lead with the most interesting or important thing you found
- Do NOT invent any facts — only summarize what is in the findings and research
- If the findings list is empty, say "Nothing significant turned up for this query in the time range covered."
- Output ONLY the summary text — no JSON, no quotes, no preamble

Research type: {digest_type}
Query: {query}
Key findings:
{signals_json}

Research notes:
{research_summary}"""


async def compose_digest(
    intent: DetectedIntent,
    all_articles: list[Article],
    signals: list[KeySignal],
    risks: list[Risk],
    opportunities: list[Opportunity],
    action_items: list[ActionItem],
    tool_traces: list[ToolTraceEntry],
    research_summary: str = "",
    reasoning_steps: list[str] | None = None,
    user_context: str = "",
) -> DigestResponse:
    """Assemble the final DigestResponse from all pipeline outputs.

    Args:
        intent: The detected intent (provides digest_type and query).
        all_articles: All deduplicated articles (used to build the sources list).
        signals: Extracted key signals.
        risks: Identified risks.
        opportunities: Identified opportunities.
        action_items: Prioritized action items.
        tool_traces: All tool call traces for the audit log.
        research_summary: The agent's research summary from the agentic loop.
        reasoning_steps: Step-by-step reasoning from the agent's research.

    Returns:
        A fully populated DigestResponse.
    """
    report_id = f"rpt_{uuid.uuid4().hex[:12]}"
    generated_at = datetime.now(tz=timezone.utc)

    executive_summary = await _generate_executive_summary(
        intent.intent_type, intent.original_query, signals, research_summary,
        user_context=user_context,
    )

    url_to_article: dict[str, Article] = {a.url: a for a in all_articles if a.url}

    scored_risks = [
        Risk(
            description=r.description,
            severity=r.severity,
            source_credibility=_score_source_credibility(r.source_urls, url_to_article),
            source_urls=r.source_urls,
        )
        for r in risks
    ]

    referenced_urls: set[str] = _collect_referenced_urls(signals, scored_risks, opportunities)
    sources = _build_sources(all_articles, referenced_urls)

    digest = DigestResponse(
        digest_type=intent.intent_type,
        query=intent.original_query,
        generated_at=generated_at,
        report_id=report_id,
        executive_summary=executive_summary,
        research_summary=research_summary,
        reasoning_steps=reasoning_steps or [],
        key_signals=signals,
        risks=scored_risks,
        opportunities=opportunities,
        action_items=action_items,
        sources=sources,
        tool_trace=tool_traces,
    )

    logger.info(
        "Composed digest report_id=%s type=%s signals=%d risks=%d opps=%d actions=%d sources=%d",
        report_id,
        intent.intent_type,
        len(signals),
        len(scored_risks),
        len(opportunities),
        len(action_items),
        len(sources),
    )
    return digest


async def _generate_executive_summary(
    digest_type: str,
    query: str,
    signals: list[KeySignal],
    research_summary: str = "",
    user_context: str = "",
) -> str:
    """Generate a concise executive summary using the LLM.

    Falls back to a safe default message if the LLM call fails.
    """
    if not signals and not research_summary:
        return "No significant developments were found in the specified time range."

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.1,
        max_tokens=256,
    )
    signals_data = [
        {"signal": s.signal, "relevance": s.relevance, "source_title": s.source_title}
        for s in signals[:8]
    ]
    context_prefix = ""
    if user_context.strip():
        context_prefix = (
            f"The person reading this: {user_context.strip()[:500]}\n"
            f"Write the overview with their perspective in mind.\n\n"
        )
    prompt = context_prefix + EXEC_SUMMARY_PROMPT.format(
        digest_type=digest_type,
        query=query,
        signals_json=json.dumps(signals_data, indent=2),
        research_summary=research_summary[:1500] if research_summary else "(none)",
    )

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        summary = response.content.strip() if isinstance(response.content, str) else str(response.content)
        sentences = summary.split(". ")
        if len(sentences) > 3:
            summary = ". ".join(sentences[:3]) + "."
        return summary
    except Exception as exc:
        logger.warning("Executive summary generation failed: %s — using fallback", exc)
        return _fallback_summary(digest_type, signals)


def _fallback_summary(digest_type: str, signals: list[KeySignal]) -> str:
    """Build a simple fallback summary without LLM."""
    if not signals:
        return "Nothing significant turned up for this query in the time range covered."
    top_signal = signals[0].signal
    return (
        f"Found {len(signals)} notable thing(s) in this {digest_type.replace('_', ' ')}. "
        f"The biggest: {top_signal}"
    )


def _collect_referenced_urls(
    signals: list[KeySignal],
    risks: list[Risk],
    opportunities: list[Opportunity],
) -> set[str]:
    """Collect all URLs that are referenced anywhere in the digest."""
    urls: set[str] = set()
    for s in signals:
        if s.source_url:
            urls.add(s.source_url)
    for r in risks:
        urls.update(r.source_urls)
    for o in opportunities:
        urls.update(o.source_urls)
    return urls


def _build_sources(
    all_articles: list[Article],
    referenced_urls: set[str],
) -> list[Source]:
    """Build the sources list, including all referenced articles.

    Articles that appear in signals/risks/opportunities are always included.
    Additional unreferenced articles are excluded to keep the sources list clean.
    """
    url_to_article: dict[str, Article] = {a.url: a for a in all_articles if a.url}
    sources: list[Source] = []

    for url in referenced_urls:
        article = url_to_article.get(url)
        if article:
            sources.append(
                Source(
                    url=article.url,
                    title=article.title,
                    published_date=article.published_date,
                    snippet=article.snippet,
                )
            )

    # Sort by published_date descending (most recent first)
    sources.sort(key=lambda s: s.published_date, reverse=True)
    return sources
