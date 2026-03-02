"""``search_company_news`` MCP tool implementation.

Constructs a targeted SerpApi news search for a specific company, optionally
filtered by topic keywords.  Delegates all middleware concerns (validation,
caching, rate limiting, error handling) to the shared middleware layer.

Middleware pipeline
-------------------
1. Validate inputs.
2. Check cache.
3. Check rate limit.
4. Build company-specific query and call SerpApi.
5. Normalise response.
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
    internal_error_response,
    rate_limit_error_response,
    upstream_error_response,
    upstream_timeout_response,
    validation_error_response,
)
from src.middleware.rate_limiter import RateLimiter
from src.middleware.validator import validate_search_company_news_inputs
from src.serpapi.client import SerpApiClient
from src.serpapi.normalizer import normalize_response

logger = logging.getLogger(__name__)


def _build_company_query(company: str, topics: list[str] | None) -> str:
    """Construct a SerpApi query string for a company search.

    Parameters
    ----------
    company:
        The company name (e.g. ``"Walmart Connect"``).
    topics:
        Optional list of topic keywords to narrow the search.

    Returns
    -------
    str
        A query string such as ``"Walmart Connect ad platform partnerships"``.
    """
    if topics:
        topic_str = " ".join(topics)
        return f"{company} {topic_str}"
    return company


async def execute_search_company_news(
    company: str,
    time_range: str = "7d",
    topics: list[str] | None = None,
    *,
    client: SerpApiClient,
    cache: ResponseCache,
    rate_limiter: RateLimiter,
) -> dict[str, Any]:
    """Search news specific to a company.

    Parameters
    ----------
    company:
        Company name to search news for (e.g. ``"Walmart Connect"``).
    time_range:
        Time range for the search (``"1d"``, ``"7d"``, ``"30d"``, ``"1y"``).
        Defaults to ``"7d"``.
    topics:
        Optional list of topic keywords to narrow the search
        (e.g. ``["ad platform", "partnerships"]``).
    client:
        Injected ``SerpApiClient`` instance.
    cache:
        Injected ``ResponseCache`` instance.
    rate_limiter:
        Injected ``RateLimiter`` instance.

    Returns
    -------
    dict
        Serialised ``NormalizedResponse`` on success, or a structured error dict.
    """
    request_id = str(uuid.uuid4())

    # 1. Validate inputs.
    errors = validate_search_company_news_inputs(company, time_range, topics)
    if errors:
        return validation_error_response(errors)

    # 2. Check cache.
    cache_params: dict[str, Any] = {
        "company": company,
        "time_range": time_range,
        "topics": sorted(topics) if topics else None,
    }
    cache_key = ResponseCache.make_key("search_company_news", cache_params)
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        logger.info("Cache HIT — search_company_news company=%r", company)
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

    # 4. Build query and call SerpApi.
    query = _build_company_query(company, topics)
    try:
        raw_response = await client.search_news(
            query=query,
            time_range=time_range,
            num_results=10,
        )
    except httpx.TimeoutException as exc:
        return upstream_timeout_response(exc, request_id)
    except httpx.HTTPStatusError as exc:
        return upstream_error_response(exc, request_id)
    except httpx.HTTPError as exc:
        logger.error("UPSTREAM_ERROR: httpx error — %s", exc)
        from src.middleware.error_handler import ErrorDetail, ErrorResponse
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

    # 5. Normalise.
    try:
        normalised = normalize_response(
            raw_response,
            query=query,
            cached=False,
            request_id=request_id,
        )
    except Exception as exc:
        return internal_error_response(exc, request_id)

    # 6. Store in cache.
    result = normalised.model_dump()
    cache.set(cache_key, result)

    logger.info(
        "search_company_news OK — company=%r results=%d request_id=%s",
        company,
        normalised.total_results,
        request_id,
    )
    return result
