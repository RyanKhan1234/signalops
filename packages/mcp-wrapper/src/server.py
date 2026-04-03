"""SignalOps MCP server definition and tool registration.

This module wires together the middleware pipeline and registers the three
MCP tools exposed to the Agent Orchestrator:

* ``search_news`` — general news search
* ``search_company_news`` — company-specific news search
* ``get_article_metadata`` — article metadata lookup

Each tool shares the same middleware pipeline:
  validate → cache check → rate limit → SerpApi → normalise → cache store → return

The server is instantiated as a module-level singleton.  Transport (stdio or
SSE) is selected at startup time via the ``MCP_TRANSPORT`` environment variable.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import TextContent, Tool

from src.config import get_config
from src.middleware.cache import ResponseCache
from src.middleware.rate_limiter import RateLimiter
from src.serpapi.client import SerpApiClient
from src.tools.get_article_metadata import execute_get_article_metadata
from src.tools.search_company_news import execute_search_company_news
from src.tools.search_news import execute_search_news

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared infrastructure (module-level singletons)
# ---------------------------------------------------------------------------

_config = get_config()

_search_cache = ResponseCache(ttl_seconds=_config.cache_ttl_seconds)
_metadata_cache = ResponseCache(ttl_seconds=_config.cache_ttl_metadata_seconds)
_rate_limiter = RateLimiter(
    per_minute=_config.rate_limit_per_minute,
    per_day=_config.rate_limit_per_day,
)
_serpapi_client = SerpApiClient(
    api_key=_config.serpapi_api_key,
    base_url=_config.serpapi_base_url,
)

# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

server: Server = Server("signalops-news")


# ---------------------------------------------------------------------------
# Tool: list_tools
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the schema for all registered MCP tools."""
    return [
        Tool(
            name="search_news",
            description=(
                "Search recent news articles for a query. "
                "Returns a normalised list of articles with title, URL, source, "
                "published date, and snippet."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "The search query (max 200 chars). "
                            "E.g. 'AI model releases this week'."
                        ),
                    },
                    "time_range": {
                        "type": "string",
                        "enum": ["1d", "7d", "30d", "1y"],
                        "default": "7d",
                        "description": "Time range for the search.",
                    },
                    "num_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 10,
                        "description": "Number of results to return.",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="search_company_news",
            description=(
                "Search news specific to a company. "
                "Optionally filter by topic keywords. "
                "Returns a normalised list of articles."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": (
                            "Company name to search for (max 200 chars). "
                            "E.g. 'Anthropic'."
                        ),
                    },
                    "time_range": {
                        "type": "string",
                        "enum": ["1d", "7d", "30d", "1y"],
                        "default": "7d",
                        "description": "Time range for the search.",
                    },
                    "topics": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 100},
                        "description": (
                            "Optional list of topic keywords to narrow the search. "
                            "E.g. ['safety', 'regulation']."
                        ),
                    },
                },
                "required": ["company"],
            },
        ),
        Tool(
            name="get_article_metadata",
            description=(
                "Fetch metadata for a specific article URL. "
                "Returns title, source, published date, and snippet."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "format": "uri",
                        "description": "The full HTTP/HTTPS URL of the article.",
                    },
                },
                "required": ["url"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool: call_tool
# ---------------------------------------------------------------------------


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch a tool call to the appropriate handler.

    All tools return a JSON-serialisable dict that is wrapped in a
    ``TextContent`` block so the MCP framework can transmit it.
    """
    import json

    logger.info("Tool called: %s args=%r", name, arguments)

    result: dict[str, Any]

    if name == "search_news":
        result = await execute_search_news(
            query=arguments.get("query", ""),
            time_range=arguments.get("time_range", "7d"),
            num_results=arguments.get("num_results", 10),
            client=_serpapi_client,
            cache=_search_cache,
            rate_limiter=_rate_limiter,
        )

    elif name == "search_company_news":
        result = await execute_search_company_news(
            company=arguments.get("company", ""),
            time_range=arguments.get("time_range", "7d"),
            topics=arguments.get("topics"),
            client=_serpapi_client,
            cache=_search_cache,
            rate_limiter=_rate_limiter,
        )

    elif name == "get_article_metadata":
        result = await execute_get_article_metadata(
            url=arguments.get("url", ""),
            client=_serpapi_client,
            cache=_metadata_cache,
            rate_limiter=_rate_limiter,
        )

    else:
        result = {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": f"Unknown tool: {name!r}",
                "details": {},
                "retry_after_seconds": None,
            }
        }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]
