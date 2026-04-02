"""Digest composer for the Agent Orchestrator.

Assembles the final structured DigestResponse from processed article data.
Generates the executive summary and ensures all source references are populated.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from anthropic import AsyncAnthropic

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


EXEC_SUMMARY_PROMPT = """You are a research analyst writing an executive summary.
Given the digest type, query, and list of key signals, write a concise 2-3 sentence executive summary.

Rules:
- Maximum 3 sentences
- Focus on the most important business impact
- Do NOT invent any facts — only summarize what is in the signals
- If signals list is empty, say "No significant competitive activity was detected in the specified time range."
- Output ONLY the summary text — no JSON, no quotes, no preamble

Digest type: {digest_type}
Query: {query}
Key signals:
{signals_json}"""


async def compose_digest(
    intent: DetectedIntent,
    all_articles: list[Article],
    signals: list[KeySignal],
    risks: list[Risk],
    opportunities: list[Opportunity],
    action_items: list[ActionItem],
    tool_traces: list[ToolTraceEntry],
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

    Returns:
        A fully populated DigestResponse.
    """
    report_id = f"rpt_{uuid.uuid4().hex[:12]}"
    generated_at = datetime.now(tz=timezone.utc)

    # Generate executive summary
    executive_summary = await _generate_executive_summary(
        intent.intent_type, intent.original_query, signals
    )

    # Build URL → Article lookup for credibility scoring and source building
    url_to_article: dict[str, Article] = {a.url: a for a in all_articles if a.url}

    # Score source credibility on each risk
    scored_risks = [
        Risk(
            description=r.description,
            severity=r.severity,
            source_credibility=_score_source_credibility(r.source_urls, url_to_article),
            source_urls=r.source_urls,
        )
        for r in risks
    ]

    # Build sources list from all articles that are actually referenced
    referenced_urls: set[str] = _collect_referenced_urls(signals, scored_risks, opportunities)
    sources = _build_sources(all_articles, referenced_urls)

    digest = DigestResponse(
        digest_type=intent.intent_type,
        query=intent.original_query,
        generated_at=generated_at,
        report_id=report_id,
        executive_summary=executive_summary,
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
) -> str:
    """Generate a concise executive summary using the LLM.

    Falls back to a safe default message if the LLM call fails.
    """
    if not signals:
        return "No significant competitive activity was detected in the specified time range."

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    signals_data = [
        {"signal": s.signal, "relevance": s.relevance, "source_title": s.source_title}
        for s in signals[:8]  # cap to avoid exceeding token limits
    ]
    prompt = EXEC_SUMMARY_PROMPT.format(
        digest_type=digest_type,
        query=query,
        signals_json=json.dumps(signals_data, indent=2),
    )

    try:
        message = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        summary = message.content[0].text.strip()
        # Enforce sentence count (trim to 3 sentences)
        sentences = summary.split(". ")
        if len(sentences) > 3:
            summary = ". ".join(sentences[:3]) + "."
        return summary
    except Exception as exc:
        logger.warning("Executive summary generation failed: %s — using fallback", exc)
        return _fallback_summary(digest_type, signals)


def _fallback_summary(digest_type: str, signals: list[KeySignal]) -> str:
    """Build a simple fallback executive summary without LLM."""
    if not signals:
        return "No significant competitive activity was detected in the specified time range."
    top_signal = signals[0].signal
    return (
        f"This {digest_type.replace('_', ' ')} identified {len(signals)} key signal(s). "
        f"The most significant: {top_signal}"
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
