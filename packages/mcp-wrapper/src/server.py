"""SignalOps MCP server definition and tool registration.

This module wires together the middleware pipeline and registers all MCP tools
exposed to the Agent Orchestrator.

**Data gathering tools** (external API calls):
* ``search_news``            — general news search (Google News)
* ``search_company_news``    — company-specific news search
* ``get_article_metadata``   — article metadata lookup
* ``search_web``             — general Google web search
* ``search_scholar``         — Google Scholar academic search
* ``search_finance``         — Google Finance market data
* ``find_videos``            — YouTube video search
* ``search_github``          — GitHub repository search
* ``search_reddit``          — Reddit post search
* ``search_quora``           — Quora Q&A search
* ``fetch_page``             — fetch and extract text from a URL

**Analytical tools** (local computation, no external API calls):
* ``analyze_sentiment``      — NLP sentiment scoring with key phrase extraction
* ``extract_entities``       — regex-based named entity recognition (NER)
* ``compare_sources``        — cross-reference 2-3 articles for agreement/divergence
* ``query_past_research``    — search traceability store for past digests
* ``calculate_trend``        — multi-window mention frequency trend computation
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import TextContent, Tool

from src.config import get_config
from src.dispatch import dispatch_tool
from src.middleware.cache import ResponseCache
from src.middleware.rate_limiter import RateLimiter
from src.serpapi.client import SerpApiClient

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
                        "description": "The search query (max 200 chars).",
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
                "Optionally filter by topic keywords."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "Company name to search for (max 200 chars).",
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
                        "description": "Optional topic keywords to narrow the search.",
                    },
                },
                "required": ["company"],
            },
        ),
        Tool(
            name="get_article_metadata",
            description="Fetch metadata for a specific article URL.",
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
        Tool(
            name="search_web",
            description=(
                "General Google web search. Returns organic results including "
                "blog posts, analyses, documentation, and other web pages."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (max 200 chars).",
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
            name="search_scholar",
            description=(
                "Search Google Scholar for academic papers and research. "
                "Best for AI, science, and technical topics."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The academic search query (max 200 chars).",
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
            name="search_finance",
            description=(
                "Search Google Finance for market data on a stock ticker or company. "
                "Returns price, market cap, and key financial metrics."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Ticker symbol or company name (max 200 chars). "
                            "E.g. 'AAPL:NASDAQ' or 'Apple Inc'."
                        ),
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="find_videos",
            description=(
                "Search YouTube for videos. "
                "Returns video titles, channel names, and links."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The video search query (max 200 chars).",
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
            name="search_github",
            description=(
                "Search GitHub repositories. "
                "Returns repo names, descriptions, star counts, and languages. "
                "Best for tracking open-source projects and tech activity."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The repository search query (max 200 chars).",
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
            name="search_reddit",
            description=(
                "Search Reddit posts and discussions. "
                "Returns post titles, subreddits, and content. "
                "Best for community sentiment, opinions, and practical experiences."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (max 200 chars).",
                    },
                    "subreddit": {
                        "type": "string",
                        "description": (
                            "Optional subreddit to restrict search to "
                            "(e.g. 'MachineLearning'). Max 50 chars."
                        ),
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
            name="search_quora",
            description=(
                "Search Quora for Q&A content. "
                "Returns questions and answers. "
                "Best for explanatory content and expert opinions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (max 200 chars).",
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
            name="fetch_page",
            description=(
                "Fetch a web page and extract its plain-text content. "
                "Returns title, text content (up to 5000 chars), and metadata. "
                "Use this to read the full content of a specific article or page."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "format": "uri",
                        "description": "The full HTTP/HTTPS URL to fetch.",
                    },
                },
                "required": ["url"],
            },
        ),
        # --- Analytical / computational tools ---
        Tool(
            name="analyze_sentiment",
            description=(
                "Run NLP sentiment analysis on a block of text. "
                "Returns sentiment score, label, confidence, and key phrases. "
                "This is a computational tool — no external API calls."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to analyze for sentiment.",
                    },
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="extract_entities",
            description=(
                "Extract named entities from text using NER. "
                "Identifies organizations, people, technologies, monetary "
                "amounts, percentages, stock tickers, and dates."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to analyze for entity extraction.",
                    },
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="compare_sources",
            description=(
                "Cross-reference 2-3 articles by URL. Computes content "
                "similarity, shared themes, and unique angles per source."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "2-3 article URLs to compare.",
                    },
                },
                "required": ["urls"],
            },
        ),
        Tool(
            name="query_past_research",
            description=(
                "Search SignalOps archive of past digest reports for "
                "related research. Shows what was researched previously."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Topic or keywords to search past digests.",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="calculate_trend",
            description=(
                "Calculate mention frequency trend across 24h/7d/30d windows. "
                "Returns article counts, daily rates, acceleration, and trend label."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The topic to calculate trends for.",
                    },
                },
                "required": ["query"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool: call_tool
# ---------------------------------------------------------------------------


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch a tool call to the appropriate handler."""
    import json

    logger.info("Tool called: %s args=%r", name, arguments)

    result = await dispatch_tool(
        name,
        arguments,
        serpapi_client=_serpapi_client,
        search_cache=_search_cache,
        metadata_cache=_metadata_cache,
        rate_limiter=_rate_limiter,
    )

    return [TextContent(type="text", text=json.dumps(result, indent=2))]
