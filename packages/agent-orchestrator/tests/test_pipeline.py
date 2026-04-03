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
        "title": "OpenAI Expands Self-Serve Ad Platform",
        "url": "https://example.com/walmart-connect-self-serve",
        "source": "TechCrunch",
        "published_date": "2026-03-01",
        "snippet": "OpenAI announced major expansions to its self-serve advertising platform.",
        "thumbnail_url": None,
    },
    {
        "title": "OpenAI Q1 2026 Revenue Up 35%",
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
        "snippet": "Competition in the AI research network space is intensifying.",
        "thumbnail_url": None,
    },
]

MOCK_MCP_RESPONSE = {
    "articles": MOCK_ARTICLES,
    "query": "OpenAI",
    "total_results": 3,
    "cached": False,
    "request_id": "req_mock_123",
}

MOCK_KNOWN_URLS = {a["url"] for a in MOCK_ARTICLES}


def make_anthropic_text_message(content: str) -> MagicMock:
    """Create a mock Anthropic API message response with text content."""
    mock_content = MagicMock()
    mock_content.type = "text"
    mock_content.text = content
    mock_message = MagicMock()
    mock_message.content = [mock_content]
    mock_message.stop_reason = "end_turn"
    return mock_message


def make_anthropic_tool_use_message(tool_calls: list[dict]) -> MagicMock:
    """Create a mock Anthropic API message with tool_use blocks."""
    blocks = []
    for i, tc in enumerate(tool_calls):
        block = MagicMock()
        block.type = "tool_use"
        block.id = f"toolu_{i:04d}"
        block.name = tc["name"]
        block.input = tc["input"]
        blocks.append(block)
    mock_message = MagicMock()
    mock_message.content = blocks
    mock_message.stop_reason = "tool_use"
    return mock_message


def make_anthropic_research_done_message(summary: str) -> MagicMock:
    """Create a mock Anthropic response where the agent finishes research."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = summary
    mock_message = MagicMock()
    mock_message.content = [text_block]
    mock_message.stop_reason = "end_turn"
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
                arguments={"company": "OpenAI", "time_range": "7d"},
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

            mock_http.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

            call = PlannedToolCall(
                tool_name="search_company_news",
                arguments={"company": "OpenAI", "time_range": "7d"},
                parallel_group=0,
            )

            async with MCPClient() as client:
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result, trace = await client.call_tool(call)

            assert result.articles == []
            assert trace.status == "error"
            assert trace.error is not None


# ---------------------------------------------------------------------------
# Researcher loop tests
# ---------------------------------------------------------------------------


class TestResearcherLoop:
    """Tests for the agentic research loop."""

    @pytest.mark.asyncio
    async def test_research_loop_calls_tools_and_returns_results(self) -> None:
        """The research loop should call tools, gather articles, and produce a summary."""
        from src.agent.researcher import run_research_loop
        from src.models.digest import DetectedIntent

        intent = DetectedIntent(
            intent_type="deep_dive",
            entities=["OpenAI"],
            time_range="7d",
            original_query="Tell me about OpenAI",
        )

        # First call: Claude returns tool_use
        tool_use_response = make_anthropic_tool_use_message([
            {"name": "search_company_news", "input": {"company": "OpenAI", "time_range": "7d"}},
            {"name": "search_reddit", "input": {"query": "OpenAI discussion"}},
        ])

        # Second call: Claude returns end_turn with summary
        done_response = make_anthropic_research_done_message(
            "I found 3 articles about OpenAI's recent platform expansion and strong Q1 results."
        )

        llm_call_count = 0

        async def mock_llm(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal llm_call_count
            llm_call_count += 1
            if llm_call_count == 1:
                return tool_use_response
            return done_response

        mock_mcp_response = MagicMock()
        mock_mcp_response.status_code = 200
        mock_mcp_response.json.return_value = MOCK_MCP_RESPONSE

        with (
            patch("anthropic.AsyncAnthropic") as mock_anthropic_cls,
            patch("httpx.AsyncClient") as mock_http_cls,
        ):
            mock_anthropic = AsyncMock()
            mock_anthropic_cls.return_value = mock_anthropic
            mock_anthropic.messages.create = AsyncMock(side_effect=mock_llm)

            mock_http = AsyncMock()
            mock_http_cls.return_value.__aenter__.return_value = mock_http
            mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_mcp_response)

            result = await run_research_loop(intent=intent, correlation_id="test-123")

        assert len(result.articles) > 0
        assert len(result.tool_traces) == 2
        assert "OpenAI" in result.research_summary
        assert llm_call_count == 2

    @pytest.mark.asyncio
    async def test_research_loop_emits_stream_events(self) -> None:
        """The research loop should emit events when a callback is provided."""
        from src.agent.researcher import run_research_loop
        from src.models.digest import DetectedIntent

        intent = DetectedIntent(
            intent_type="latest_news",
            entities=["Tesla"],
            time_range="1d",
            original_query="Tesla news today",
        )

        tool_use_response = make_anthropic_tool_use_message([
            {"name": "search_news", "input": {"query": "Tesla latest news", "time_range": "1d"}},
        ])
        done_response = make_anthropic_research_done_message("Found Tesla news.")

        call_count = 0

        async def mock_llm(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            return tool_use_response if call_count == 1 else done_response

        mock_mcp_response = MagicMock()
        mock_mcp_response.status_code = 200
        mock_mcp_response.json.return_value = MOCK_MCP_RESPONSE

        events: list[tuple[str, dict]] = []

        def on_event(event: str, data: dict) -> None:
            events.append((event, data))

        with (
            patch("anthropic.AsyncAnthropic") as mock_anthropic_cls,
            patch("httpx.AsyncClient") as mock_http_cls,
        ):
            mock_anthropic = AsyncMock()
            mock_anthropic_cls.return_value = mock_anthropic
            mock_anthropic.messages.create = AsyncMock(side_effect=mock_llm)

            mock_http = AsyncMock()
            mock_http_cls.return_value.__aenter__.return_value = mock_http
            mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_mcp_response)

            await run_research_loop(intent=intent, correlation_id="test-stream", on_event=on_event)

        event_types = [e[0] for e in events]
        assert "tool_call" in event_types
        assert "tool_result" in event_types

    @pytest.mark.asyncio
    async def test_research_loop_respects_max_iterations(self) -> None:
        """The loop must stop after max_research_iterations even if Claude keeps requesting tools."""
        from src.agent.researcher import run_research_loop
        from src.models.digest import DetectedIntent

        intent = DetectedIntent(
            intent_type="deep_dive",
            entities=["Test"],
            time_range="7d",
            original_query="Test",
        )

        tool_response = make_anthropic_tool_use_message([
            {"name": "search_news", "input": {"query": "test"}},
        ])

        mock_mcp_response = MagicMock()
        mock_mcp_response.status_code = 200
        mock_mcp_response.json.return_value = MOCK_MCP_RESPONSE

        with (
            patch("anthropic.AsyncAnthropic") as mock_anthropic_cls,
            patch("httpx.AsyncClient") as mock_http_cls,
            patch("src.agent.researcher.settings") as mock_settings,
        ):
            mock_settings.anthropic_api_key = "test"
            mock_settings.research_model = "test-model"
            mock_settings.max_research_iterations = 3

            mock_anthropic = AsyncMock()
            mock_anthropic_cls.return_value = mock_anthropic
            mock_anthropic.messages.create = AsyncMock(return_value=tool_response)

            mock_http = AsyncMock()
            mock_http_cls.return_value.__aenter__.return_value = mock_http
            mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_mcp_response)

            result = await run_research_loop(intent=intent)

        assert mock_anthropic.messages.create.call_count == 3
        assert "maximum" in result.research_summary.lower()


# ---------------------------------------------------------------------------
# Full pipeline integration tests with mocked LLM and MCP
# ---------------------------------------------------------------------------


class TestFullPipelineMocked:
    """End-to-end pipeline tests using mocked external dependencies."""

    @pytest.mark.asyncio
    async def test_pipeline_produces_valid_digest(self) -> None:
        """Full pipeline: mocked research loop + mocked processing -> valid DigestResponse."""
        from src.agent.orchestrator import run_pipeline

        intent_response = json.dumps({
            "intent_type": "deep_dive",
            "entities": ["OpenAI"],
            "time_range": "7d",
            "original_query": "Anything important about OpenAI this week?",
        })

        # Research loop: first call returns tool_use, second returns end_turn
        research_tool_use = make_anthropic_tool_use_message([
            {"name": "search_company_news", "input": {"company": "OpenAI", "time_range": "7d"}},
        ])
        research_done = make_anthropic_research_done_message(
            "Found key developments in OpenAI's platform expansion and Q1 revenue growth."
        )

        cluster_response = json.dumps({
            "clusters": [
                {"theme": "Platform Updates", "article_indices": [0, 2]},
                {"theme": "Financial Results", "article_indices": [1]},
            ]
        })

        signal_response = json.dumps({
            "signal": "OpenAI expanded self-serve with new targeting.",
            "relevance": "high",
            "best_article_index": 0,
        })

        risk_opp_response = json.dumps({
            "risks": [{
                "description": "Self-serve expansion pressures competitor margins.",
                "severity": "high",
                "signal_indices": [0],
            }],
            "opportunities": [{
                "description": "API integrations create partnership opportunities.",
                "confidence": "medium",
                "signal_indices": [0],
            }],
        })

        action_response = json.dumps({
            "action_items": [{
                "action": "Conduct competitive pricing analysis.",
                "priority": "P0",
                "rationale": "35% revenue growth signals market share gains.",
            }]
        })

        summary_response = (
            "OpenAI reported strong Q1 2026 results with 35% revenue growth while expanding "
            "its self-serve platform."
        )

        # Build the sequence of LLM calls in order
        llm_responses = [
            make_anthropic_text_message(intent_response),   # intent detection
            research_tool_use,                                # research loop: tool_use
            research_done,                                    # research loop: end_turn
            make_anthropic_text_message(cluster_response),   # clustering
            make_anthropic_text_message(signal_response),    # signals (cluster 1)
            make_anthropic_text_message(signal_response),    # signals (cluster 2)
            make_anthropic_text_message(risk_opp_response),  # risks/opps
            make_anthropic_text_message(action_response),    # actions
            make_anthropic_text_message(summary_response),   # exec summary
        ]

        call_count = 0

        async def mock_llm_create(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            idx = min(call_count, len(llm_responses) - 1)
            call_count += 1
            return llm_responses[idx]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_MCP_RESPONSE

        with (
            patch("anthropic.AsyncAnthropic") as mock_anthropic_cls,
            patch("httpx.AsyncClient") as mock_http_cls,
            patch("src.services.traceability.TraceabilityClient.log_report", new_callable=AsyncMock),
        ):
            mock_anthropic = AsyncMock()
            mock_anthropic_cls.return_value = mock_anthropic
            mock_anthropic.messages.create = AsyncMock(side_effect=mock_llm_create)

            mock_http = AsyncMock()
            mock_http_cls.return_value.__aenter__.return_value = mock_http
            mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(return_value=mock_response)

            digest = await run_pipeline(
                prompt="Anything important about OpenAI this week?",
                correlation_id="test-correlation-123",
            )

        assert isinstance(digest, DigestResponse)
        assert digest.digest_type == "deep_dive"
        assert digest.query == "Anything important about OpenAI this week?"
        assert digest.report_id.startswith("rpt_")
        assert digest.executive_summary
        assert digest.generated_at is not None
        assert digest.research_summary != ""

    @pytest.mark.asyncio
    async def test_pipeline_handles_mcp_failure_gracefully(self) -> None:
        """Pipeline should complete even if all MCP tool calls fail."""
        import httpx
        from src.agent.orchestrator import run_pipeline

        intent_response = json.dumps({
            "intent_type": "deep_dive",
            "entities": ["OpenAI"],
            "time_range": "7d",
            "original_query": "OpenAI this week?",
        })

        # Research loop: tool_use then end_turn (even with failed tools)
        research_tool_use = make_anthropic_tool_use_message([
            {"name": "search_company_news", "input": {"company": "OpenAI"}},
        ])
        research_done = make_anthropic_research_done_message(
            "Tool calls failed. No results available."
        )

        llm_responses = [
            make_anthropic_text_message(intent_response),
            research_tool_use,
            research_done,
        ]
        call_count = 0

        async def mock_llm_create(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            idx = min(call_count, len(llm_responses) - 1)
            call_count += 1
            return llm_responses[idx]

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
            mock_http.post = AsyncMock(side_effect=httpx.ConnectError("MCP Wrapper down"))

            digest = await run_pipeline(
                prompt="OpenAI this week?",
                correlation_id="test-fail-123",
            )

        assert isinstance(digest, DigestResponse)

    @pytest.mark.asyncio
    async def test_guardrails_drop_hallucinated_signal(self) -> None:
        """Guardrails must drop a signal whose source_url is not in any MCP result."""
        from src.agent.guardrails import collect_known_urls, validate_and_sanitize
        from src.models.digest import (
            DigestResponse,
            KeySignal,
            Source,
        )

        hallucinated_url = "https://hallucinated.com/fake-article"
        real_url = "https://example.com/walmart-connect-self-serve"

        digest = DigestResponse(
            digest_type="deep_dive",
            query="OpenAI this week?",
            generated_at=datetime.now(tz=timezone.utc),
            report_id="rpt_guardrail_test",
            executive_summary="Test summary",
            key_signals=[
                KeySignal(
                    signal="Hallucinated claim about OpenAI.",
                    source_url=hallucinated_url,
                    source_title="Fake Article",
                    published_date="2026-03-01",
                    relevance="high",
                ),
                KeySignal(
                    signal="Real claim about OpenAI self-serve expansion.",
                    source_url=real_url,
                    source_title="OpenAI Expands Self-Serve",
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

        mcp_result = MCPToolResult(
            articles=[
                Article(
                    title="OpenAI Expands Self-Serve",
                    url=real_url,
                    source="TechCrunch",
                    published_date="2026-03-01",
                    snippet="real article",
                )
            ],
            query="OpenAI",
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
    """Tests for the FastAPI /health, /digest, and /digest/stream endpoints."""

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
        assert response.status_code == 422

    def test_digest_endpoint_validates_missing_prompt(self, client: TestClient) -> None:
        response = client.post("/digest", json={})
        assert response.status_code == 422

    def test_digest_endpoint_propagates_correlation_id(self, client: TestClient) -> None:
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
                json={"prompt": "OpenAI this week?"},
                headers={"X-Request-ID": "my-correlation-123"},
            )

        assert response.headers.get("X-Request-ID") == "my-correlation-123"

    def test_digest_endpoint_returns_valid_schema(self, client: TestClient) -> None:
        with patch("src.api.routes.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
            mock_pipeline.return_value = DigestResponse(
                digest_type="deep_dive",
                query="Anything important about OpenAI this week?",
                generated_at=datetime.now(tz=timezone.utc),
                report_id="rpt_abc123",
                executive_summary="OpenAI reported strong Q1 2026 results.",
                key_signals=[],
                risks=[],
                opportunities=[],
                action_items=[],
                sources=[],
                tool_trace=[],
            )
            response = client.post(
                "/digest",
                json={"prompt": "Anything important about OpenAI this week?"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["digest_type"] == "deep_dive"
        assert data["report_id"] == "rpt_abc123"
        assert "executive_summary" in data
        assert "research_summary" in data
        assert "reasoning_steps" in data
        assert "key_signals" in data
        assert "risks" in data
        assert "opportunities" in data
        assert "action_items" in data
        assert "sources" in data
        assert "tool_trace" in data

    def test_digest_endpoint_handles_runtime_error(self, client: TestClient) -> None:
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
        with patch("src.api.routes.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
            mock_pipeline.side_effect = RuntimeError("Tool execution failed: MCP Wrapper down")
            response = client.post(
                "/digest",
                json={"prompt": "Test prompt"},
            )

        assert response.status_code == 503
        data = response.json()
        assert data["error"]["code"] == "UPSTREAM_UNAVAILABLE"

    def test_stream_endpoint_validates_empty_prompt(self, client: TestClient) -> None:
        response = client.post("/digest/stream", json={"prompt": ""})
        assert response.status_code == 422

    def test_stream_endpoint_returns_sse_content_type(self, client: TestClient) -> None:
        with patch("src.api.routes.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
            mock_pipeline.return_value = DigestResponse(
                digest_type="deep_dive",
                query="test",
                generated_at=datetime.now(tz=timezone.utc),
                report_id="rpt_stream_test",
                executive_summary="Test.",
                key_signals=[],
                risks=[],
                opportunities=[],
                action_items=[],
                sources=[],
                tool_trace=[],
            )
            response = client.post(
                "/digest/stream",
                json={"prompt": "Test streaming"},
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
