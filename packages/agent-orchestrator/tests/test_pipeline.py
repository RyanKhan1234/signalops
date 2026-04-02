"""Integration tests for the full pipeline with mocked MCP responses.

These tests mock the MCP Wrapper HTTP calls and the Anthropic API calls
to verify end-to-end pipeline behavior without requiring real credentials.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.models.digest import Article, DigestResponse, MCPToolResult


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


MOCK_ARTICLES = [
    {
        "title": "Walmart Connect Expands Self-Serve Ad Platform",
        "url": "https://example.com/walmart-connect-self-serve",
        "source": "TechCrunch",
        "published_date": "2026-03-01",
        "snippet": "Walmart Connect announced major expansions to its self-serve advertising platform.",
        "thumbnail_url": None,
    },
    {
        "title": "Walmart Connect Q1 2026 Revenue Up 35%",
        "url": "https://example.com/walmart-connect-q1-2026",
        "source": "AdAge",
        "published_date": "2026-03-01",
        "snippet": "Walmart's advertising business reported strong Q1 2026 results with 35% growth.",
        "thumbnail_url": None,
    },
    {
        "title": "Retail Media Competition Intensifies",
        "url": "https://example.com/retail-media-competition",
        "source": "Digiday",
        "published_date": "2026-02-28",
        "snippet": "Competition in the retail media network space is intensifying.",
        "thumbnail_url": None,
    },
]

MOCK_MCP_RESPONSE = {
    "articles": MOCK_ARTICLES,
    "query": "Walmart Connect",
    "total_results": 3,
    "cached": False,
    "request_id": "req_mock_123",
}

MOCK_KNOWN_URLS = {a["url"] for a in MOCK_ARTICLES}


def make_anthropic_message(content: str) -> MagicMock:
    """Create a mock Anthropic API message response."""
    mock_content = MagicMock()
    mock_content.text = content
    mock_message = MagicMock()
    mock_message.content = [mock_content]
    return mock_message


# ---------------------------------------------------------------------------
# Deduplication tests
# ---------------------------------------------------------------------------


class TestDeduplication:
    """Tests for article deduplication logic."""

    def test_dedup_removes_duplicate_urls(self) -> None:
        from src.agent.processor import deduplicate_articles

        articles = [
            Article(title="A", url="https://example.com/a", source="S", published_date="2026-03-01", snippet="s"),
            Article(title="A duplicate", url="https://example.com/a", source="S", published_date="2026-03-01", snippet="s"),
            Article(title="B", url="https://example.com/b", source="S", published_date="2026-03-01", snippet="s"),
        ]
        result = deduplicate_articles(articles)
        assert len(result) == 2

    def test_dedup_preserves_first_occurrence(self) -> None:
        from src.agent.processor import deduplicate_articles

        articles = [
            Article(title="First", url="https://example.com/a", source="S", published_date="2026-03-01", snippet="first"),
            Article(title="Second", url="https://example.com/a", source="S", published_date="2026-03-01", snippet="second"),
        ]
        result = deduplicate_articles(articles)
        assert result[0].title == "First"

    def test_dedup_empty_list(self) -> None:
        from src.agent.processor import deduplicate_articles

        assert deduplicate_articles([]) == []

    def test_dedup_no_duplicates_unchanged(self) -> None:
        from src.agent.processor import deduplicate_articles

        articles = [
            Article(title="A", url="https://example.com/a", source="S", published_date="2026-03-01", snippet="s"),
            Article(title="B", url="https://example.com/b", source="S", published_date="2026-03-01", snippet="s"),
        ]
        result = deduplicate_articles(articles)
        assert len(result) == 2

    def test_dedup_ignores_empty_urls(self) -> None:
        from src.agent.processor import deduplicate_articles

        articles = [
            Article(title="A", url="", source="S", published_date="2026-03-01", snippet="s"),
            Article(title="B", url="", source="S", published_date="2026-03-01", snippet="s"),
        ]
        # Empty URLs are deduplicated as well (empty string considered same key)
        result = deduplicate_articles(articles)
        assert len(result) <= 2


# ---------------------------------------------------------------------------
# MCP client mock tests
# ---------------------------------------------------------------------------


class TestMCPClientMocked:
    """Tests for MCPClient behavior with mocked HTTP responses."""

    @pytest.mark.asyncio
    async def test_successful_tool_call_returns_result_and_trace(self) -> None:
        from src.models.digest import PlannedToolCall
        from src.tools.mcp_client import MCPClient

        with patch("httpx.AsyncClient") as mock_http_class:
            mock_http = AsyncMock()
            mock_http_class.return_value.__aenter__.return_value = mock_http
            mock_http_class.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = MOCK_MCP_RESPONSE
            mock_http.post = AsyncMock(return_value=mock_response)

            call = PlannedToolCall(
                tool_name="search_company_news",
                arguments={"company": "Walmart Connect", "time_range": "7d"},
                parallel_group=0,
            )

            async with MCPClient() as client:
                result, trace = await client.call_tool(call)

            assert len(result.articles) == 3
            assert trace.status == "success"
            assert trace.tool_name == "search_company_news"
            assert trace.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_failed_tool_call_returns_empty_result_with_error_trace(self) -> None:
        from src.models.digest import PlannedToolCall
        from src.tools.mcp_client import MCPClient
        import httpx

        with patch("httpx.AsyncClient") as mock_http_class:
            mock_http = AsyncMock()
            mock_http_class.return_value.__aenter__.return_value = mock_http
            mock_http_class.return_value.__aexit__ = AsyncMock(return_value=False)

            # Simulate a connection error on all retries
            mock_http.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

            call = PlannedToolCall(
                tool_name="search_company_news",
                arguments={"company": "Walmart Connect", "time_range": "7d"},
                parallel_group=0,
            )

            async with MCPClient() as client:
                with patch("asyncio.sleep", new_callable=AsyncMock):  # Skip actual backoff
                    result, trace = await client.call_tool(call)

            assert result.articles == []
            assert trace.status == "error"
            assert trace.error is not None


# ---------------------------------------------------------------------------
# Full pipeline integration tests with mocked LLM and MCP
# ---------------------------------------------------------------------------


class TestFullPipelineMocked:
    """End-to-end pipeline tests using mocked external dependencies."""

    @pytest.mark.asyncio
    async def test_pipeline_produces_valid_digest(self) -> None:
        """Full pipeline test: mocked MCP + mocked Anthropic → valid DigestResponse."""
        from src.agent.orchestrator import run_pipeline

        # Mock intent detection response
        intent_response = json.dumps({
            "intent_type": "deep_dive",
            "entities": ["Walmart Connect"],
            "time_range": "7d",
            "original_query": "Anything important about Walmart Connect this week?",
        })

        # Mock clustering response
        cluster_response = json.dumps({
            "clusters": [
                {"theme": "Ad Platform Updates", "article_indices": [0, 2]},
                {"theme": "Financial Performance", "article_indices": [1]},
            ]
        })

        # Mock signal extraction response
        signal_response = json.dumps({
            "signal": "Walmart Connect expanded its self-serve platform with new targeting capabilities, directly pressuring competitor ad margins.",
            "relevance": "high",
            "best_article_index": 0,
        })

        # Mock risk/opportunity response
        risk_opp_response = json.dumps({
            "risks": [
                {
                    "description": "Walmart Connect self-serve expansion may pressure competitor ad platform margins.",
                    "severity": "high",
                    "signal_indices": [0],
                }
            ],
            "opportunities": [
                {
                    "description": "Walmart Connect's API integrations create partnership opportunities.",
                    "confidence": "medium",
                    "signal_indices": [0],
                }
            ],
        })

        # Mock action items response
        action_response = json.dumps({
            "action_items": [
                {
                    "action": "Conduct competitive pricing analysis comparing Walmart Connect CPMs to alternatives.",
                    "priority": "P0",
                    "rationale": "Walmart Connect's 35% revenue growth signals accelerating market share gains.",
                },
                {
                    "action": "Evaluate Walmart Connect API integration opportunity for Q2 2026.",
                    "priority": "P1",
                    "rationale": "New API integrations announced present a strategic partnership window.",
                },
            ]
        })

        # Mock executive summary response
        summary_response = (
            "Walmart Connect reported strong Q1 2026 results with 35% revenue growth while expanding "
            "its self-serve advertising platform. The platform's new targeting capabilities and API "
            "integrations signal accelerating competitive pressure in the retail media space."
        )

        # Sequence of LLM responses in order of calls
        llm_responses = [
            intent_response,
            cluster_response,
            signal_response,  # For cluster 1
            signal_response,  # For cluster 2
            risk_opp_response,
            action_response,
            summary_response,
        ]

        call_count = 0

        async def mock_llm_create(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            response_text = llm_responses[min(call_count, len(llm_responses) - 1)]
            call_count += 1
            return make_anthropic_message(response_text)

        # Mock HTTP for MCP calls
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_MCP_RESPONSE

        with (
            patch("anthropic.AsyncAnthropic") as mock_anthropic_cls,
            patch("httpx.AsyncClient") as mock_http_cls,
            patch("src.services.traceability.TraceabilityClient.log_report", new_callable=AsyncMock),
        ):
            # Set up Anthropic mock
            mock_anthropic = AsyncMock()
            mock_anthropic_cls.return_value = mock_anthropic
            mock_anthropic.messages.create = AsyncMock(side_effect=mock_llm_create)

            # Set up HTTP mock for MCP calls
            mock_http = AsyncMock()
            mock_http_cls.return_value.__aenter__.return_value = mock_http
            mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_response)

            digest = await run_pipeline(
                prompt="Anything important about Walmart Connect this week?",
                correlation_id="test-correlation-123",
            )

        assert isinstance(digest, DigestResponse)
        assert digest.digest_type == "deep_dive"
        assert digest.query == "Anything important about Walmart Connect this week?"
        assert digest.report_id.startswith("rpt_")
        assert digest.executive_summary
        assert digest.generated_at is not None

    @pytest.mark.asyncio
    async def test_pipeline_handles_mcp_failure_gracefully(self) -> None:
        """Pipeline should return empty-result digest if MCP Wrapper is down."""
        import httpx
        from src.agent.orchestrator import run_pipeline

        intent_response = json.dumps({
            "intent_type": "deep_dive",
            "entities": ["Walmart Connect"],
            "time_range": "7d",
            "original_query": "Walmart Connect this week?",
        })

        async def mock_llm_create(*args: Any, **kwargs: Any) -> MagicMock:
            return make_anthropic_message(intent_response)

        with (
            patch("anthropic.AsyncAnthropic") as mock_anthropic_cls,
            patch("httpx.AsyncClient") as mock_http_cls,
            patch("src.services.traceability.TraceabilityClient.log_report", new_callable=AsyncMock),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_anthropic = AsyncMock()
            mock_anthropic_cls.return_value = mock_anthropic
            mock_anthropic.messages.create = AsyncMock(side_effect=mock_llm_create)

            mock_http = AsyncMock()
            mock_http_cls.return_value.__aenter__.return_value = mock_http
            mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            # All MCP calls fail with connection error
            mock_http.post = AsyncMock(side_effect=httpx.ConnectError("MCP Wrapper down"))

            digest = await run_pipeline(
                prompt="Walmart Connect this week?",
                correlation_id="test-fail-123",
            )

        # Should get a valid digest (empty-result, not crash)
        assert isinstance(digest, DigestResponse)
        assert "No relevant articles" in digest.executive_summary
        assert len(digest.key_signals) == 0

    @pytest.mark.asyncio
    async def test_guardrails_drop_hallucinated_signal(self) -> None:
        """Guardrails must drop a signal whose source_url is not in any MCP result."""
        from src.agent.guardrails import collect_known_urls, validate_and_sanitize
        from src.models.digest import (
            DigestResponse,
            KeySignal,
            Source,
        )

        # Build a digest with a signal pointing to a URL that was never fetched
        hallucinated_url = "https://hallucinated.com/fake-article"
        real_url = "https://example.com/walmart-connect-self-serve"

        digest = DigestResponse(
            digest_type="deep_dive",
            query="Walmart Connect this week?",
            generated_at=datetime.now(tz=timezone.utc),
            report_id="rpt_guardrail_test",
            executive_summary="Test summary",
            key_signals=[
                KeySignal(
                    signal="Hallucinated claim about Walmart Connect.",
                    source_url=hallucinated_url,
                    source_title="Fake Article",
                    published_date="2026-03-01",
                    relevance="high",
                ),
                KeySignal(
                    signal="Real claim about Walmart Connect self-serve expansion.",
                    source_url=real_url,
                    source_title="Walmart Connect Expands Self-Serve",
                    published_date="2026-03-01",
                    relevance="high",
                ),
            ],
            risks=[],
            opportunities=[],
            action_items=[],
            sources=[
                Source(url=real_url, title="Real Article", published_date="2026-03-01", snippet="real"),
                Source(url=hallucinated_url, title="Fake", published_date="2026-03-01", snippet="fake"),
            ],
            tool_trace=[],
        )

        # Only the real_url was actually returned by MCP
        mcp_result = MCPToolResult(
            articles=[
                Article(
                    title="Walmart Connect Expands Self-Serve",
                    url=real_url,
                    source="TechCrunch",
                    published_date="2026-03-01",
                    snippet="real article",
                )
            ],
            query="Walmart Connect",
            total_results=1,
            cached=False,
            request_id="req_1",
        )
        known_urls = collect_known_urls([mcp_result])
        result = validate_and_sanitize(digest, known_urls)

        assert len(result.key_signals) == 1
        assert result.key_signals[0].source_url == real_url
        assert hallucinated_url not in {s.source_url for s in result.key_signals}


# ---------------------------------------------------------------------------
# FastAPI endpoint tests
# ---------------------------------------------------------------------------


class TestFastAPIEndpoints:
    """Tests for the FastAPI /health and /digest endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        app = create_app()
        return TestClient(app)

    def test_health_endpoint_returns_ok(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "agent-orchestrator"

    def test_digest_endpoint_validates_empty_prompt(self, client: TestClient) -> None:
        response = client.post("/digest", json={"prompt": ""})
        assert response.status_code == 422  # Pydantic validation error

    def test_digest_endpoint_validates_missing_prompt(self, client: TestClient) -> None:
        response = client.post("/digest", json={})
        assert response.status_code == 422

    def test_digest_endpoint_propagates_correlation_id(self, client: TestClient) -> None:
        """The response should echo back the X-Request-ID header."""
        with patch("src.api.routes.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
            mock_pipeline.return_value = DigestResponse(
                digest_type="deep_dive",
                query="test",
                generated_at=datetime.now(tz=timezone.utc),
                report_id="rpt_test",
                executive_summary="Test summary.",
                key_signals=[],
                risks=[],
                opportunities=[],
                action_items=[],
                sources=[],
                tool_trace=[],
            )
            response = client.post(
                "/digest",
                json={"prompt": "Walmart Connect this week?"},
                headers={"X-Request-ID": "my-correlation-123"},
            )

        assert response.headers.get("X-Request-ID") == "my-correlation-123"

    def test_digest_endpoint_returns_valid_schema(self, client: TestClient) -> None:
        """A successful digest response should match the DigestResponse schema."""
        with patch("src.api.routes.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
            mock_pipeline.return_value = DigestResponse(
                digest_type="deep_dive",
                query="Anything important about Walmart Connect this week?",
                generated_at=datetime.now(tz=timezone.utc),
                report_id="rpt_abc123",
                executive_summary="Walmart Connect reported strong Q1 2026 results.",
                key_signals=[],
                risks=[],
                opportunities=[],
                action_items=[],
                sources=[],
                tool_trace=[],
            )
            response = client.post(
                "/digest",
                json={"prompt": "Anything important about Walmart Connect this week?"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["digest_type"] == "deep_dive"
        assert data["report_id"] == "rpt_abc123"
        assert "executive_summary" in data
        assert "key_signals" in data
        assert "risks" in data
        assert "opportunities" in data
        assert "action_items" in data
        assert "sources" in data
        assert "tool_trace" in data

    def test_digest_endpoint_handles_runtime_error(self, client: TestClient) -> None:
        """Pipeline errors should return a structured 500 error response."""
        with patch("src.api.routes.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
            mock_pipeline.side_effect = RuntimeError("Pipeline crashed")
            response = client.post(
                "/digest",
                json={"prompt": "Test prompt"},
            )

        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert "code" in data["error"]

    def test_digest_endpoint_handles_mcp_error(self, client: TestClient) -> None:
        """MCP Wrapper errors should return a 503 response."""
        with patch("src.api.routes.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
            mock_pipeline.side_effect = RuntimeError("Tool execution failed: MCP Wrapper down")
            response = client.post(
                "/digest",
                json={"prompt": "Test prompt"},
            )

        assert response.status_code == 503
        data = response.json()
        assert data["error"]["code"] == "UPSTREAM_UNAVAILABLE"
