"""MCP client for calling MCP Wrapper tools over HTTP.

The MCP Wrapper exposes a JSON/HTTP API (not SSE in this implementation)
at MCP_WRAPPER_URL. This client handles all tool calls, latency tracking,
and structured error handling.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

import httpx

from src.config import settings
from src.models.digest import Article, MCPToolResult, PlannedToolCall
from src.models.trace import ToolTraceEntry

logger = logging.getLogger(__name__)

# Timeout for individual MCP tool calls (seconds)
MCP_CALL_TIMEOUT = 30.0
# Max retries on transient HTTP errors
MAX_RETRIES = 3
# Initial backoff for retries (seconds)
INITIAL_BACKOFF = 1.0


class MCPClientError(Exception):
    """Raised when an MCP tool call fails permanently."""

    def __init__(self, tool_name: str, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.tool_name = tool_name
        self.status_code = status_code


class MCPClient:
    """Async client for invoking MCP Wrapper tools.

    Handles:
    - HTTP POST to the MCP Wrapper endpoint
    - Response normalization into MCPToolResult
    - Per-call latency tracking
    - Structured error handling and retries
    """

    def __init__(
        self,
        base_url: str = settings.mcp_wrapper_url,
        correlation_id: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._correlation_id = correlation_id
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "MCPClient":
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=MCP_CALL_TIMEOUT,
            headers=self._build_headers(),
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._correlation_id:
            headers[settings.correlation_id_header] = self._correlation_id
        return headers

    async def call_tool(self, call: PlannedToolCall) -> tuple[MCPToolResult, ToolTraceEntry]:
        """Execute a single planned tool call against the MCP Wrapper.

        Args:
            call: The planned tool call with name and arguments.

        Returns:
            A tuple of (MCPToolResult, ToolTraceEntry).

        Raises:
            MCPClientError: If the tool call fails after all retries.
        """
        if self._client is None:
            raise RuntimeError("MCPClient must be used as an async context manager")

        endpoint = f"/tools/{call.tool_name}"
        start_ts = datetime.now(tz=timezone.utc)
        start_ms = time.monotonic()

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.post(endpoint, json=dict(call.arguments))
                latency_ms = int((time.monotonic() - start_ms) * 1000)

                if response.status_code == 200:
                    data = response.json()
                    result = _parse_tool_result(data)
                    trace = ToolTraceEntry(
                        tool_name=call.tool_name,
                        input=dict(call.arguments),
                        output_summary=f"Fetched {len(result.articles)} articles for query '{result.query}'",
                        latency_ms=latency_ms,
                        timestamp=start_ts,
                        status="success",
                    )
                    logger.info(
                        "MCP tool '%s' succeeded in %dms — %d articles",
                        call.tool_name,
                        latency_ms,
                        len(result.articles),
                    )
                    return result, trace

                # Non-200 responses
                error_body = _safe_json(response)
                error_msg = error_body.get("error", {}).get("message", response.text[:200])
                logger.warning(
                    "MCP tool '%s' returned HTTP %d (attempt %d/%d): %s",
                    call.tool_name,
                    response.status_code,
                    attempt + 1,
                    MAX_RETRIES,
                    error_msg,
                )
                last_error = MCPClientError(
                    tool_name=call.tool_name,
                    message=error_msg,
                    status_code=response.status_code,
                )
                # Do not retry on 4xx (client errors)
                if 400 <= response.status_code < 500:
                    break

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                latency_ms = int((time.monotonic() - start_ms) * 1000)
                logger.warning(
                    "MCP tool '%s' network error (attempt %d/%d): %s",
                    call.tool_name,
                    attempt + 1,
                    MAX_RETRIES,
                    exc,
                )
                last_error = exc

            # Exponential backoff before retry
            if attempt < MAX_RETRIES - 1:
                backoff = INITIAL_BACKOFF * (2**attempt)
                await asyncio.sleep(backoff)

        # All retries exhausted — return an error trace with empty result
        latency_ms = int((time.monotonic() - start_ms) * 1000)
        error_message = str(last_error) if last_error else "Unknown error"
        trace = ToolTraceEntry(
            tool_name=call.tool_name,
            input=dict(call.arguments),
            output_summary=f"FAILED: {error_message}",
            latency_ms=latency_ms,
            timestamp=start_ts,
            status="error",
            error=error_message,
        )
        empty_result = MCPToolResult(
            articles=[],
            query=str(call.arguments.get("query", call.arguments.get("company", ""))),
            total_results=0,
            cached=False,
            request_id="",
        )
        logger.error(
            "MCP tool '%s' failed after %d attempts: %s",
            call.tool_name,
            MAX_RETRIES,
            error_message,
        )
        return empty_result, trace

    async def call_tools_parallel(
        self, calls: list[PlannedToolCall]
    ) -> list[tuple[MCPToolResult, ToolTraceEntry]]:
        """Execute multiple tool calls concurrently.

        Groups calls by parallel_group and executes each group together,
        then proceeds to the next group in ascending order.

        Args:
            calls: List of planned tool calls with parallel_group assignments.

        Returns:
            List of (MCPToolResult, ToolTraceEntry) tuples in call order.
        """
        if not calls:
            return []

        # Sort calls by group
        sorted_calls = sorted(calls, key=lambda c: c.parallel_group)
        groups: dict[int, list[PlannedToolCall]] = {}
        for call in sorted_calls:
            groups.setdefault(call.parallel_group, []).append(call)

        all_results: list[tuple[MCPToolResult, ToolTraceEntry]] = []
        for group_id in sorted(groups.keys()):
            group_calls = groups[group_id]
            logger.debug(
                "Executing parallel group %d with %d calls", group_id, len(group_calls)
            )
            tasks = [self.call_tool(call) for call in group_calls]
            group_results = await asyncio.gather(*tasks)
            all_results.extend(group_results)

        return all_results


# ---------------------------------------------------------------------------
# Response parsing helpers
# ---------------------------------------------------------------------------


def _parse_tool_result(data: dict[str, object]) -> MCPToolResult:
    """Parse a raw MCP Wrapper response into a MCPToolResult."""
    raw_articles = data.get("articles", [])
    articles: list[Article] = []
    for raw in raw_articles if isinstance(raw_articles, list) else []:
        if isinstance(raw, dict):
            articles.append(
                Article(
                    title=str(raw.get("title", "")),
                    url=str(raw.get("url", "")),
                    source=str(raw.get("source", "")),
                    published_date=str(raw.get("published_date", "")),
                    snippet=str(raw.get("snippet", "")),
                    thumbnail_url=raw.get("thumbnail_url"),  # type: ignore[arg-type]
                )
            )
    return MCPToolResult(
        articles=articles,
        query=str(data.get("query", "")),
        total_results=int(data.get("total_results", len(articles))),
        cached=bool(data.get("cached", False)),
        request_id=str(data.get("request_id", "")),
    )


def _safe_json(response: httpx.Response) -> dict[str, object]:
    """Try to parse a response as JSON; return empty dict on failure."""
    try:
        return response.json()  # type: ignore[no-any-return]
    except Exception:
        return {}
