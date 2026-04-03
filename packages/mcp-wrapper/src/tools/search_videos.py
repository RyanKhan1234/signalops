"""``search_videos`` MCP tool implementation.

Searches YouTube via SerpApi and returns a normalised list of video results.
Follows the same middleware pipeline as all other MCP tools.

Middleware pipeline
-------------------
1. Validate inputs.
2. Check cache (return cached response if hit).
3. Check rate limit.
4. Call SerpApi (YouTube engine).
5. Normalise ``video_results``.
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
from src.middleware.validator import validate_search_videos_inputs
from src.serpapi.client import SerpApiClient
from src.serpapi.normalizer import normalize_video_results

logger = logging.getLogger(__name__)


async def execute_search_videos(
    query: str,
    num_results: int = 10,
    *,
    client: SerpApiClient,
    cache: ResponseCache,
    rate_limiter: RateLimiter,
) -> dict[str, Any]:
    """Search YouTube for videos matching a query.

    Parameters
    ----------
    query:
        The search query string (max 200 characters).
    num_results:
        Number of results to return (1–50). Defaults to 10.
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
    errors = validate_search_videos_inputs(query, num_results)
    if errors:
        return validation_error_response(errors)

    # 2. Check cache.
    cache_key = ResponseCache.make_key(
        "search_videos",
        {"query": query, "num_results": num_results},
    )
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        logger.info("Cache HIT — search_videos query=%r", query)
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
        raw_response = await client.search_videos(
            query=query,
            num_results=num_results,
        )
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

    # 5. Normalise.
    try:
        normalised = normalize_video_results(
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
        "search_videos OK — query=%r results=%d request_id=%s",
        query,
        normalised.total_results,
        request_id,
    )
    return result
