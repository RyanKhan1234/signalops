"""Tests for the guardrails validation module."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.agent.guardrails import (
    GuardrailsValidationError,
    collect_known_urls,
    validate_and_sanitize,
)
from src.models.digest import (
    ActionItem,
    Article,
    DigestResponse,
    KeySignal,
    MCPToolResult,
    Opportunity,
    Risk,
    Source,
)
from tests.conftest import make_article, make_mcp_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_digest(
    signals: list[KeySignal] | None = None,
    risks: list[Risk] | None = None,
    opportunities: list[Opportunity] | None = None,
    action_items: list[ActionItem] | None = None,
    sources: list[Source] | None = None,
    executive_summary: str = "Test summary",
) -> DigestResponse:
    """Helper to build a minimal DigestResponse for testing."""
    return DigestResponse(
        digest_type="deep_dive",
        query="Test query",
        generated_at=datetime.now(tz=timezone.utc),
        report_id="rpt_test123",
        executive_summary=executive_summary,
        key_signals=signals or [],
        risks=risks or [],
        opportunities=opportunities or [],
        action_items=action_items or [],
        sources=sources or [],
        tool_trace=[],
    )


KNOWN_URL = "https://example.com/article-1"
UNKNOWN_URL = "https://example.com/unknown-article"


# ---------------------------------------------------------------------------
# collect_known_urls tests
# ---------------------------------------------------------------------------


class TestCollectKnownUrls:
    """Tests for the collect_known_urls helper."""

    def test_collects_urls_from_mcp_results(self) -> None:
        result = make_mcp_result()
        known = collect_known_urls([result])
        assert "https://example.com/walmart-connect-self-serve" in known
        assert "https://example.com/walmart-connect-q1-2026" in known

    def test_handles_empty_results_list(self) -> None:
        known = collect_known_urls([])
        assert known == set()

    def test_handles_empty_articles(self) -> None:
        result = make_mcp_result(articles=[])
        known = collect_known_urls([result])
        assert known == set()

    def test_deduplicates_urls_across_results(self) -> None:
        result1 = make_mcp_result(articles=[make_article(url="https://example.com/a")])
        result2 = make_mcp_result(articles=[make_article(url="https://example.com/a")])
        known = collect_known_urls([result1, result2])
        assert len(known) == 1


# ---------------------------------------------------------------------------
# validate_and_sanitize tests
# ---------------------------------------------------------------------------


class TestValidateAndSanitize:
    """Tests for the main guardrails validation function."""

    def test_valid_digest_passes_unchanged(self) -> None:
        """A digest where all URLs are known should pass through cleanly."""
        digest = make_digest(
            signals=[
                KeySignal(
                    signal="OpenAI expanded self-serve.",
                    source_url=KNOWN_URL,
                    source_title="Test Article",
                    published_date="2026-03-01",
                    relevance="high",
                )
            ],
            sources=[
                Source(
                    url=KNOWN_URL,
                    title="Test Article",
                    published_date="2026-03-01",
                    snippet="Test snippet",
                )
            ],
        )
        result = validate_and_sanitize(digest, {KNOWN_URL})
        assert len(result.key_signals) == 1
        assert result.key_signals[0].source_url == KNOWN_URL

    def test_signal_with_unknown_url_is_dropped(self) -> None:
        """A signal whose source_url is not in known_urls must be dropped."""
        digest = make_digest(
            signals=[
                KeySignal(
                    signal="Hallucinated signal.",
                    source_url=UNKNOWN_URL,
                    source_title="Fake Article",
                    published_date="2026-03-01",
                    relevance="high",
                )
            ],
            sources=[
                Source(
                    url=UNKNOWN_URL,
                    title="Fake Article",
                    published_date="2026-03-01",
                    snippet="fake",
                )
            ],
        )
        result = validate_and_sanitize(digest, {KNOWN_URL})
        # Either empty result digest or the signal is dropped
        assert len(result.key_signals) == 0

    def test_risk_with_unknown_urls_is_dropped(self) -> None:
        """A risk with no known source URLs must be dropped."""
        digest = make_digest(
            risks=[
                Risk(
                    description="Fake risk.",
                    severity="high",
                    source_urls=[UNKNOWN_URL],
                )
            ],
            sources=[
                Source(
                    url=UNKNOWN_URL,
                    title="Fake",
                    published_date="2026-03-01",
                    snippet="fake",
                )
            ],
        )
        result = validate_and_sanitize(digest, {KNOWN_URL})
        assert len(result.risks) == 0

    def test_risk_with_mixed_urls_keeps_known_only(self) -> None:
        """A risk with both known and unknown URLs retains only the known URLs."""
        digest = make_digest(
            signals=[
                KeySignal(
                    signal="Real signal.",
                    source_url=KNOWN_URL,
                    source_title="Real Article",
                    published_date="2026-03-01",
                    relevance="high",
                )
            ],
            risks=[
                Risk(
                    description="Partially attributed risk.",
                    severity="medium",
                    source_urls=[KNOWN_URL, UNKNOWN_URL],
                )
            ],
            sources=[
                Source(url=KNOWN_URL, title="Real", published_date="2026-03-01", snippet="real"),
                Source(url=UNKNOWN_URL, title="Fake", published_date="2026-03-01", snippet="fake"),
            ],
        )
        result = validate_and_sanitize(digest, {KNOWN_URL})
        assert len(result.risks) == 1
        assert KNOWN_URL in result.risks[0].source_urls
        assert UNKNOWN_URL not in result.risks[0].source_urls

    def test_opportunity_with_unknown_url_is_dropped(self) -> None:
        digest = make_digest(
            opportunities=[
                Opportunity(
                    description="Fake opportunity.",
                    confidence="high",
                    source_urls=[UNKNOWN_URL],
                )
            ],
            sources=[
                Source(url=UNKNOWN_URL, title="Fake", published_date="2026-03-01", snippet="fake")
            ],
        )
        result = validate_and_sanitize(digest, {KNOWN_URL})
        assert len(result.opportunities) == 0

    def test_empty_known_urls_returns_empty_result_digest(self) -> None:
        """If no articles were found (empty known_urls), return the empty-result digest."""
        digest = make_digest(
            signals=[
                KeySignal(
                    signal="Some signal.",
                    source_url=KNOWN_URL,
                    source_title="Test",
                    published_date="2026-03-01",
                    relevance="high",
                )
            ],
        )
        result = validate_and_sanitize(digest, set())
        assert result.executive_summary == "No relevant articles found for this query in the specified time range."
        assert len(result.key_signals) == 0
        assert len(result.risks) == 0
        assert len(result.opportunities) == 0

    def test_missing_report_id_raises_validation_error(self) -> None:
        digest = DigestResponse(
            digest_type="deep_dive",
            query="test",
            generated_at=datetime.now(tz=timezone.utc),
            report_id="",  # Missing!
            executive_summary="test",
            key_signals=[],
            risks=[],
            opportunities=[],
            action_items=[],
            sources=[],
            tool_trace=[],
        )
        with pytest.raises(GuardrailsValidationError):
            validate_and_sanitize(digest, {KNOWN_URL})

    def test_missing_query_raises_validation_error(self) -> None:
        digest = DigestResponse(
            digest_type="deep_dive",
            query="",  # Missing!
            generated_at=datetime.now(tz=timezone.utc),
            report_id="rpt_test",
            executive_summary="test",
            key_signals=[],
            risks=[],
            opportunities=[],
            action_items=[],
            sources=[],
            tool_trace=[],
        )
        with pytest.raises(GuardrailsValidationError):
            validate_and_sanitize(digest, {KNOWN_URL})

    def test_sources_list_filtered_to_referenced_only(self) -> None:
        """The sources list should only contain URLs that appear in signals/risks/opps."""
        unreferenced_url = "https://example.com/unreferenced"
        digest = make_digest(
            signals=[
                KeySignal(
                    signal="Real signal.",
                    source_url=KNOWN_URL,
                    source_title="Real",
                    published_date="2026-03-01",
                    relevance="high",
                )
            ],
            sources=[
                Source(url=KNOWN_URL, title="Real", published_date="2026-03-01", snippet="real"),
                Source(url=unreferenced_url, title="Extra", published_date="2026-03-01", snippet="extra"),
            ],
        )
        known = {KNOWN_URL, unreferenced_url}
        result = validate_and_sanitize(digest, known)
        source_urls = {s.url for s in result.sources}
        assert KNOWN_URL in source_urls
        assert unreferenced_url not in source_urls

    def test_all_content_dropped_returns_empty_result(self) -> None:
        """If guardrails drop all signals, risks, and opps, return empty-result digest."""
        digest = make_digest(
            signals=[
                KeySignal(
                    signal="Hallucinated.",
                    source_url=UNKNOWN_URL,
                    source_title="Fake",
                    published_date="2026-03-01",
                    relevance="high",
                )
            ],
            sources=[
                Source(url=UNKNOWN_URL, title="Fake", published_date="2026-03-01", snippet="fake")
            ],
        )
        result = validate_and_sanitize(digest, {KNOWN_URL})
        assert len(result.key_signals) == 0
        assert "No fully-attributed" in result.executive_summary or "No relevant" in result.executive_summary

    def test_valid_digest_preserves_executive_summary(self) -> None:
        expected_summary = "Key competitive developments this week."
        digest = make_digest(
            signals=[
                KeySignal(
                    signal="Signal text.",
                    source_url=KNOWN_URL,
                    source_title="Real",
                    published_date="2026-03-01",
                    relevance="medium",
                )
            ],
            sources=[
                Source(url=KNOWN_URL, title="Real", published_date="2026-03-01", snippet="real")
            ],
            executive_summary=expected_summary,
        )
        result = validate_and_sanitize(digest, {KNOWN_URL})
        assert result.executive_summary == expected_summary
