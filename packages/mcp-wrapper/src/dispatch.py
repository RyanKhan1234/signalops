"""Shared tool dispatch for the MCP Wrapper.

Both the MCP ``call_tool`` handler and the REST ``POST /tools/{name}``
endpoint delegate here so the tool wiring stays in one place.
"""

from __future__ import annotations

import logging
from typing import Any

from src.middleware.cache import ResponseCache
from src.middleware.rate_limiter import RateLimiter
from src.serpapi.client import SerpApiClient
from src.tools.analyze_sentiment import execute_analyze_sentiment
from src.tools.calculate_trend import execute_calculate_trend
from src.tools.compare_sources import execute_compare_sources
from src.tools.extract_entities import execute_extract_entities
from src.tools.fetch_page import execute_fetch_page
from src.tools.get_article_metadata import execute_get_article_metadata
from src.tools.query_past_research import execute_query_past_research
from src.tools.search_company_news import execute_search_company_news
from src.tools.search_finance import execute_search_finance
from src.tools.search_github import execute_search_github
from src.tools.search_news import execute_search_news
from src.tools.search_quora import execute_search_quora
from src.tools.search_reddit import execute_search_reddit
from src.tools.search_scholar import execute_search_scholar
from src.tools.find_videos import execute_find_videos
from src.tools.search_web import execute_search_web

logger = logging.getLogger(__name__)


async def dispatch_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    serpapi_client: SerpApiClient,
    search_cache: ResponseCache,
    metadata_cache: ResponseCache,
    rate_limiter: RateLimiter,
) -> dict[str, Any]:
    """Route a tool call to the correct handler and return the raw dict result."""

    if name == "search_news":
        return await execute_search_news(
            query=arguments.get("query", ""),
            time_range=arguments.get("time_range", "7d"),
            num_results=arguments.get("num_results", 10),
            client=serpapi_client,
            cache=search_cache,
            rate_limiter=rate_limiter,
        )

    if name == "search_company_news":
        return await execute_search_company_news(
            company=arguments.get("company", ""),
            time_range=arguments.get("time_range", "7d"),
            topics=arguments.get("topics"),
            client=serpapi_client,
            cache=search_cache,
            rate_limiter=rate_limiter,
        )

    if name == "get_article_metadata":
        return await execute_get_article_metadata(
            url=arguments.get("url", ""),
            client=serpapi_client,
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )

    if name == "search_web":
        return await execute_search_web(
            query=arguments.get("query", ""),
            num_results=arguments.get("num_results", 10),
            client=serpapi_client,
            cache=search_cache,
            rate_limiter=rate_limiter,
        )

    if name == "search_scholar":
        return await execute_search_scholar(
            query=arguments.get("query", ""),
            num_results=arguments.get("num_results", 10),
            client=serpapi_client,
            cache=search_cache,
            rate_limiter=rate_limiter,
        )

    if name == "search_finance":
        return await execute_search_finance(
            query=arguments.get("query", ""),
            client=serpapi_client,
            cache=search_cache,
            rate_limiter=rate_limiter,
        )

    if name == "find_videos":
        return await execute_find_videos(
            query=arguments.get("query", ""),
            num_results=arguments.get("num_results", 10),
            client=serpapi_client,
            cache=search_cache,
            rate_limiter=rate_limiter,
        )

    if name == "search_github":
        return await execute_search_github(
            query=arguments.get("query", ""),
            num_results=arguments.get("num_results", 10),
            cache=search_cache,
            rate_limiter=rate_limiter,
        )

    if name == "search_reddit":
        return await execute_search_reddit(
            query=arguments.get("query", ""),
            subreddit=arguments.get("subreddit"),
            num_results=arguments.get("num_results", 10),
            cache=search_cache,
            rate_limiter=rate_limiter,
        )

    if name == "search_quora":
        return await execute_search_quora(
            query=arguments.get("query", ""),
            num_results=arguments.get("num_results", 10),
            client=serpapi_client,
            cache=search_cache,
            rate_limiter=rate_limiter,
        )

    if name == "fetch_page":
        return await execute_fetch_page(
            url=arguments.get("url", ""),
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )

    # --- Analytical / computational tools ---

    if name == "analyze_sentiment":
        return await execute_analyze_sentiment(
            text=arguments.get("text", ""),
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )

    if name == "extract_entities":
        return await execute_extract_entities(
            text=arguments.get("text", ""),
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )

    if name == "compare_sources":
        return await execute_compare_sources(
            urls=arguments.get("urls", []),
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )

    if name == "query_past_research":
        return await execute_query_past_research(
            query=arguments.get("query", ""),
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )

    if name == "calculate_trend":
        return await execute_calculate_trend(
            query=arguments.get("query", ""),
            client=serpapi_client,
            cache=search_cache,
            rate_limiter=rate_limiter,
        )

    return {
        "error": {
            "code": "UNKNOWN_TOOL",
            "message": f"Unknown tool: {name!r}",
            "details": {},
            "retry_after_seconds": None,
        }
    }
