"""``search_finance`` MCP tool implementation.

Fetches Google Finance market data for a financial instrument via SerpApi
and returns a normalised single-article response summarising key metrics.

Middleware pipeline
-------------------
1. Validate inputs.
2. Check cache (return cached response if hit).
3. Check rate limit.
4. Call SerpApi (google_finance engine).
5. Extract summary/knowledge_graph fields into a normalised response.
6. Store in cache.
7. Return normalised response.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx

from src.middleware.cache import ResponseCache
from src.middleware.error_handler import (
    ErrorDetail,
    ErrorResponse,
    internal_error_response,
    rate_limit_error_response,
    upstream_error_response,
    upstream_timeout_response,
    validation_error_response,
)
from src.middleware.rate_limiter import RateLimiter
from src.middleware.validator import validate_search_finance_inputs
from src.serpapi.client import SerpApiClient
from src.serpapi.models import NormalizedArticle, NormalizedResponse, SerpApiResponse
from src.serpapi.normalizer import _now_iso  # noqa: PLC2701 — shared utility

logger = logging.getLogger(__name__)


def _build_finance_snippet(raw: SerpApiResponse) -> str:
    """Build a human-readable snippet from Google Finance response fields.

    Extracts whatever financial metrics are available from the ``summary``
    and ``knowledge_graph`` sections of the SerpApi response.

    Parameters
    ----------
    raw:
        The parsed SerpApi response from the google_finance engine.

    Returns
    -------
    str
        A plain-text summary of available financial metrics.
    """
    parts: list[str] = []

    # ``summary`` is the primary source of structured finance data.
    summary: dict[str, Any] = raw.model_extra.get("summary") or {}
    if summary:
        if summary.get("price"):
            parts.append(f"Price: {summary['price']}")
        if summary.get("price_change"):
            parts.append(f"Change: {summary['price_change']}")
        if summary.get("price_change_percent"):
            parts.append(f"Change%: {summary['price_change_percent']}")
        if summary.get("currency"):
            parts.append(f"Currency: {summary['currency']}")
        if summary.get("exchange"):
            parts.append(f"Exchange: {summary['exchange']}")
        if summary.get("market_cap"):
            parts.append(f"Market Cap: {summary['market_cap']}")

    # ``knowledge_graph`` may hold additional fields.
    kg: dict[str, Any] = raw.model_extra.get("knowledge_graph") or {}
    if kg:
        if kg.get("market_cap") and "Market Cap" not in " ".join(parts):
            parts.append(f"Market Cap: {kg['market_cap']}")
        if kg.get("price_range_52_weeks"):
            parts.append(f"52-week range: {kg['price_range_52_weeks']}")
        if kg.get("pe_ratio"):
            parts.append(f"P/E ratio: {kg['pe_ratio']}")

    if not parts:
        return "No financial metrics available for this query."

    return " | ".join(parts)


async def execute_search_finance(
    query: str,
    *,
    client: SerpApiClient,
    cache: ResponseCache,
    rate_limiter: RateLimiter,
) -> dict[str, Any]:
    """Fetch Google Finance market data for a financial instrument.

    Parameters
    ----------
    query:
        The financial instrument to look up (e.g. ``"AAPL:NASDAQ"``).
    client:
        Injected ``SerpApiClient`` instance.
    cache:
        Injected ``ResponseCache`` instance.
    rate_limiter:
        Injected ``RateLimiter`` instance.

    Returns
    -------
    dict
        Serialised ``NormalizedResponse`` with one synthetic article
        summarising available financial metrics, or a structured error dict.
    """
    request_id = str(uuid.uuid4())

    # 1. Validate inputs.
    errors = validate_search_finance_inputs(query)
    if errors:
        return validation_error_response(errors)

    # 2. Check cache.
    cache_key = ResponseCache.make_key("search_finance", {"query": query})
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        logger.info("Cache HIT — search_finance query=%r", query)
        cached_value["cached"] = True
        cached_value["request_id"] = request_id
        return cached_value

    # 3. Rate limit check.
    limit_error = rate_limiter.check()
    if limit_error:
        return rate_limit_error_response(
            limit_error.retry_after_seconds,
            limit_error.limit_type,
        )

    # 4. Call SerpApi.
    try:
        raw_response = await client.search_finance(query=query)
    except httpx.TimeoutException as exc:
        return upstream_timeout_response(exc, request_id)
    except httpx.HTTPStatusError as exc:
        return upstream_error_response(exc, request_id)
    except httpx.HTTPError as exc:
        logger.error("UPSTREAM_ERROR: httpx error — %s", exc)
        resp = ErrorResponse(
            error=ErrorDetail(
                code="UPSTREAM_ERROR",
                message=f"HTTP error contacting SerpApi: {type(exc).__name__}",
                details={"exception_type": type(exc).__name__, "request_id": request_id},
            )
        )
        return resp.model_dump()
    except Exception as exc:
        return internal_error_response(exc, request_id)

    # 5. Build a single synthetic article from finance summary fields.
    try:
        snippet = _build_finance_snippet(raw_response)
        article = NormalizedArticle(
            title=f"{query} — Financial Overview",
            url=f"https://www.google.com/finance/quote/{query}",
            source="Google Finance",
            published_date=_now_iso(),
            snippet=snippet,
            thumbnail_url=None,
        )
        normalised = NormalizedResponse(
            articles=[article],
            query=query,
            total_results=1,
            cached=False,
            request_id=request_id,
        )
    except Exception as exc:
        return internal_error_response(exc, request_id)

    # 6. Store in cache.
    result = normalised.model_dump()
    cache.set(cache_key, result)

    logger.info(
        "search_finance OK — query=%r request_id=%s",
        query,
        request_id,
    )
    return result
