"""Guardrails validation for the Agent Orchestrator.

This is the most critical module. It enforces:
1. Source attribution — every signal, risk, and opportunity must have a source URL
   that was actually returned by a tool call.
2. URL integrity — every URL in signals/risks/opportunities must exist in sources.
3. Empty result handling — if no articles are found, return an empty-result digest.
4. Schema validation — the entire digest must conform to DigestResponse.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.models.digest import (
    ActionItem,
    DigestResponse,
    KeySignal,
    Opportunity,
    Risk,
    Source,
)

logger = logging.getLogger(__name__)


class GuardrailsValidationError(Exception):
    """Raised when guardrails validation fails and cannot be auto-corrected."""

    def __init__(self, message: str, violations: list[str]) -> None:
        super().__init__(message)
        self.violations = violations


def validate_and_sanitize(
    digest: DigestResponse,
    known_urls: set[str],
) -> DigestResponse:
    """Validate the digest and sanitize it to enforce source attribution.

    This function applies all guardrail rules. Rather than raising errors
    for individual violations, it drops unattributed content and logs warnings.
    If the result is too degraded (no signals and no articles), it returns
    an empty-result digest.

    Args:
        digest: The composed digest to validate.
        known_urls: Set of all URLs actually returned by MCP tool calls.

    Returns:
        A validated and sanitized DigestResponse.

    Raises:
        GuardrailsValidationError: Only if the digest is fundamentally invalid
            (e.g., report_id is missing) and cannot be auto-corrected.
    """
    violations: list[str] = []

    # Rule 1: Basic structural integrity
    if not digest.report_id:
        raise GuardrailsValidationError(
            "Digest is missing report_id", ["Missing report_id"]
        )
    if not digest.query:
        raise GuardrailsValidationError(
            "Digest is missing query", ["Missing query"]
        )

    # Rule 2: If no articles at all, return canonical empty-result digest
    if not known_urls:
        logger.warning(
            "No articles found for query '%s' — returning empty-result digest",
            digest.query,
        )
        return _empty_result_digest(digest)

    # Rule 3: Filter key_signals — each must have a source_url in known_urls
    clean_signals: list[KeySignal] = []
    for signal in digest.key_signals:
        if signal.source_url in known_urls:
            clean_signals.append(signal)
        else:
            msg = (
                f"Signal '{signal.signal[:60]}...' dropped — "
                f"source_url '{signal.source_url}' not in known MCP results"
            )
            violations.append(msg)
            logger.warning("GUARDRAIL: %s", msg)

    # Rule 4: Filter risks — each source_url must be in known_urls
    clean_risks: list[Risk] = []
    for risk in digest.risks:
        clean_urls = [url for url in risk.source_urls if url in known_urls]
        if clean_urls:
            clean_risks.append(
                Risk(
                    description=risk.description,
                    severity=risk.severity,
                    source_credibility=risk.source_credibility,
                    source_urls=clean_urls,
                )
            )
        else:
            msg = (
                f"Risk '{risk.description[:60]}...' dropped — "
                "none of its source_urls were found in known MCP results"
            )
            violations.append(msg)
            logger.warning("GUARDRAIL: %s", msg)

    # Rule 5: Filter opportunities — each source_url must be in known_urls
    clean_opportunities: list[Opportunity] = []
    for opp in digest.opportunities:
        clean_urls = [url for url in opp.source_urls if url in known_urls]
        if clean_urls:
            clean_opportunities.append(
                Opportunity(
                    description=opp.description,
                    confidence=opp.confidence,
                    source_urls=clean_urls,
                )
            )
        else:
            msg = (
                f"Opportunity '{opp.description[:60]}...' dropped — "
                "none of its source_urls were found in known MCP results"
            )
            violations.append(msg)
            logger.warning("GUARDRAIL: %s", msg)

    # Rule 6: Rebuild sources to include ONLY URLs referenced in the clean outputs
    referenced_urls: set[str] = set()
    for s in clean_signals:
        referenced_urls.add(s.source_url)
    for r in clean_risks:
        referenced_urls.update(r.source_urls)
    for o in clean_opportunities:
        referenced_urls.update(o.source_urls)

    # Keep only sources that are actually referenced
    clean_sources: list[Source] = [
        s for s in digest.sources if s.url in referenced_urls
    ]

    # Rule 7: Verify every referenced URL has a corresponding source entry
    source_url_set = {s.url for s in clean_sources}
    missing_from_sources = referenced_urls - source_url_set
    if missing_from_sources:
        # This can happen if composer missed adding an article to sources.
        # We drop signals/risks/opps that reference missing URLs rather than
        # fabricating source entries.
        for missing_url in missing_from_sources:
            msg = f"URL '{missing_url}' referenced in digest but not in sources — dropping references"
            violations.append(msg)
            logger.warning("GUARDRAIL: %s", msg)

        # Re-filter to remove any remaining references to missing URLs
        clean_signals = [s for s in clean_signals if s.source_url in source_url_set]
        clean_risks = [
            Risk(
                description=r.description,
                severity=r.severity,
                source_credibility=r.source_credibility,
                source_urls=[u for u in r.source_urls if u in source_url_set],
            )
            for r in clean_risks
            if any(u in source_url_set for u in r.source_urls)
        ]
        clean_opportunities = [
            Opportunity(
                description=o.description,
                confidence=o.confidence,
                source_urls=[u for u in o.source_urls if u in source_url_set],
            )
            for o in clean_opportunities
            if any(u in source_url_set for u in o.source_urls)
        ]

    # Rule 8: If guardrails dropped everything, return empty-result digest
    if not clean_signals and not clean_risks and not clean_opportunities:
        logger.warning(
            "Guardrails dropped all content for query '%s' — returning empty-result digest. "
            "Violations: %s",
            digest.query,
            violations,
        )
        return _empty_result_digest(digest)

    # Rule 9: Action items do not reference URLs directly, but we validate
    # that there are risks/opps to justify them
    clean_action_items: list[ActionItem] = []
    if clean_risks or clean_opportunities:
        clean_action_items = digest.action_items  # Keep as-is; they reference risks/opps by content

    if violations:
        logger.info(
            "Guardrails applied %d correction(s) to digest %s",
            len(violations),
            digest.report_id,
        )

    # Rebuild executive summary if all signals were dropped
    executive_summary = digest.executive_summary
    if not clean_signals:
        executive_summary = (
            "No fully-attributed competitive signals were found for this query "
            "in the specified time range."
        )

    return DigestResponse(
        digest_type=digest.digest_type,
        query=digest.query,
        generated_at=digest.generated_at,
        report_id=digest.report_id,
        executive_summary=executive_summary,
        key_signals=clean_signals,
        risks=clean_risks,
        opportunities=clean_opportunities,
        action_items=clean_action_items,
        sources=clean_sources,
        tool_trace=digest.tool_trace,
    )


def _empty_result_digest(digest: DigestResponse) -> DigestResponse:
    """Return a canonical empty-result digest (no hallucinations, no fabricated content)."""
    return DigestResponse(
        digest_type=digest.digest_type,
        query=digest.query,
        generated_at=digest.generated_at if digest.generated_at else datetime.now(tz=timezone.utc),
        report_id=digest.report_id,
        executive_summary="No relevant articles found for this query in the specified time range.",
        key_signals=[],
        risks=[],
        opportunities=[],
        action_items=[],
        sources=[],
        tool_trace=digest.tool_trace,
    )


def collect_known_urls(tool_results: list[object]) -> set[str]:
    """Extract all article URLs from MCP tool results.

    Args:
        tool_results: List of MCPToolResult objects from tool execution.

    Returns:
        Set of all known URLs that were actually returned by tool calls.
    """
    known: set[str] = set()
    for result in tool_results:
        # Duck-typed access to support both real MCPToolResult and mocks
        articles = getattr(result, "articles", [])
        for article in articles:
            url = getattr(article, "url", None)
            if url:
                known.add(url)
    return known
