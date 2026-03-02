"""``get_article_metadata`` MCP tool implementation.

Fetches metadata (title, source, published date, snippet) for a specific
article URL by querying SerpApi.  Uses a longer cache TTL (1 hour) since
article metadata is stable once published.

Middleware pipeline
-------------------
1. Validate URL input.
2. Check cache (1-hour TTL for metadata).
3. Check rate limit.
4. Query SerpApi for the URL.
5. Normalise and return first matching result.
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
from src.middleware.validator import validate_get_article_metadata_inputs
from src.serpapi.client import SerpApiClient
from src.serpapi.normalizer import normalize_response

logger = logging.getLogger(__name__)

# Metadata cache uses a separate (longer) TTL — 1 hour by default.
# We pass a dedicated ResponseCache for metadata to the tool.


async def execute_get_article_metadata(
    url: str,
    *,
    client: SerpApiClient,
    cache: ResponseCache,
    rate_limiter: RateLimiter,
) -> dict[str, Any]:
    """Fetch metadata for a specific article URL.

    Parameters
    ----------
    url:
        The full HTTP/HTTPS URL of the article.
    client:
        Injected ``SerpApiClient`` instance.
    cache:
        Injected ``ResponseCache`` instance (should have 1-hour TTL).
    rate_limiter:
        Injected ``RateLimiter`` instance.

    Returns
    -------
    dict
        Serialised ``NormalizedResponse`` containing metadata for the article
        (typically 1 result), or a structured error dict.
    """
    request_id = str(uuid.uuid4())

    # 1. Validate input.
    errors = validate_get_article_metadata_inputs(url)
    if errors:
        return validation_error_response(errors)

    # 2. Check cache.
    cache_key = ResponseCache.make_key("get_article_metadata", {"url": url})
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        logger.info("Cache HIT — get_article_metadata url=%r", url)
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

    # 4. Query SerpApi.
    try:
        raw_response = await client.get_article_metadata(url=url)
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

    # 5. Normalise — use the URL as the query label for traceability.
    try:
        normalised = normalize_response(
            raw_response,
            query=url,
            cached=False,
            request_id=request_id,
        )
    except Exception as exc:
        return internal_error_response(exc, request_id)

    # 6. Store in cache.
    result = normalised.model_dump()
    cache.set(cache_key, result)

    logger.info(
        "get_article_metadata OK — url=%r results=%d request_id=%s",
        url,
        normalised.total_results,
        request_id,
    )
    return result
