"""``calculate_trend_metrics`` MCP tool — multi-window trend computation.

Runs the same search query across multiple time windows (1d, 7d, 30d)
and computes mention frequency trends. Returns whether coverage is
accelerating, stable, or declining — with velocity metrics.

This is a genuine analytical tool: it uses search as input but performs
statistical computation to derive trend signals.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.middleware.cache import ResponseCache
from src.middleware.rate_limiter import RateLimiter
from src.serpapi.client import SerpApiClient
from src.serpapi.models import NormalizedArticle, NormalizedResponse
from src.tools.search_news import execute_search_news

logger = logging.getLogger(__name__)

_TIME_WINDOWS = [
    ("1d", "Last 24 hours"),
    ("7d", "Last 7 days"),
    ("30d", "Last 30 days"),
]


async def execute_calculate_trend(
    query: str,
    *,
    client: SerpApiClient,
    cache: ResponseCache,
    rate_limiter: RateLimiter,
) -> dict[str, Any]:
    """Calculate mention frequency trend for a topic across time windows.

    Parameters
    ----------
    query:
        The topic to track trend for.
    """
    request_id = str(uuid.uuid4())

    if not query or not query.strip():
        from src.middleware.error_handler import validation_error_response
        return validation_error_response([("query", "Query is required")])

    window_counts: dict[str, int] = {}

    for window_code, window_label in _TIME_WINDOWS:
        try:
            result = await execute_search_news(
                query=query,
                time_range=window_code,
                num_results=50,
                client=client,
                cache=cache,
                rate_limiter=rate_limiter,
            )
            articles = result.get("articles", [])
            window_counts[window_code] = len(articles)
        except Exception as exc:
            logger.warning("Trend calc failed for window %s: %s", window_code, exc)
            window_counts[window_code] = -1

    count_1d = window_counts.get("1d", 0)
    count_7d = window_counts.get("7d", 0)
    count_30d = window_counts.get("30d", 0)

    daily_rate_7d = count_7d / 7 if count_7d > 0 else 0
    daily_rate_30d = count_30d / 30 if count_30d > 0 else 0

    if daily_rate_30d > 0:
        acceleration = round((daily_rate_7d - daily_rate_30d) / daily_rate_30d * 100, 1)
    else:
        acceleration = 0.0

    if count_1d > 0 and daily_rate_7d > 0:
        recency_spike = round(count_1d / daily_rate_7d, 2)
    else:
        recency_spike = 0.0

    if acceleration > 50 or recency_spike > 2.0:
        trend = "SURGING"
        trend_detail = "Coverage is accelerating significantly"
    elif acceleration > 15:
        trend = "GROWING"
        trend_detail = "Coverage is increasing above baseline"
    elif acceleration > -15:
        trend = "STABLE"
        trend_detail = "Coverage is consistent across time windows"
    elif acceleration > -50:
        trend = "DECLINING"
        trend_detail = "Coverage is decreasing from recent peaks"
    else:
        trend = "FADING"
        trend_detail = "Coverage has dropped off substantially"

    snippet_lines = [
        f"TREND: {trend} — {trend_detail}",
        "",
        "MENTION FREQUENCY:",
        f"  Last 24h: {count_1d} articles",
        f"  Last 7d:  {count_7d} articles ({daily_rate_7d:.1f}/day avg)",
        f"  Last 30d: {count_30d} articles ({daily_rate_30d:.1f}/day avg)",
        "",
        "VELOCITY METRICS:",
        f"  7d vs 30d acceleration: {acceleration:+.1f}%",
        f"  24h recency spike: {recency_spike:.1f}x daily average",
    ]

    if recency_spike > 2.0:
        snippet_lines.append("  *** Breaking: Today's coverage is significantly above normal ***")
    elif count_1d == 0 and count_7d > 5:
        snippet_lines.append("  Note: No articles in last 24h despite active week — possible lull")

    snippet = "\n".join(snippet_lines)
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    response = NormalizedResponse(
        articles=[
            NormalizedArticle(
                title=f"Trend Analysis: '{query}' — {trend}",
                url=f"analysis://trend/{request_id}",
                source="SignalOps Trend Engine",
                published_date=now,
                snippet=snippet,
            )
        ],
        query=query,
        total_results=1,
        cached=False,
        request_id=request_id,
    )
    return response.model_dump()
