"""``search_reddit`` MCP tool implementation.

Searches Reddit posts using the public Reddit JSON API (no API key required).
Returns a normalised list of post results.

Middleware pipeline
-------------------
1. Validate inputs.
2. Check cache (return cached response if hit).
3. Check rate limit.
4. Call Reddit JSON API directly.
5. Normalise post results to NormalizedResponse.
6. Store in cache.
7. Return normalised response.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
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
from src.middleware.validator import validate_search_reddit_inputs
from src.serpapi.models import NormalizedArticle, NormalizedResponse

logger = logging.getLogger(__name__)

_REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"
_REDDIT_SUBREDDIT_URL = "https://www.reddit.com/r/{subreddit}/search.json"
_REDDIT_TIMEOUT = 10.0
_REDDIT_HEADERS = {
    "User-Agent": "SignalOps/1.0 (personal research tool)",
    "Accept": "application/json",
}


def _unix_to_iso(ts: float | int | None) -> str:
    """Convert a Unix UTC timestamp to an ISO 8601 string."""
    if ts is None:
        return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OSError, OverflowError):
        return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_reddit_response(
    data: dict[str, Any],
    query: str,
    request_id: str,
) -> NormalizedResponse:
    """Convert a Reddit search JSON response to NormalizedResponse."""
    children: list[dict[str, Any]] = (
        data.get("data", {}).get("children") or []
    )
    articles: list[NormalizedArticle] = []
    seen_urls: set[str] = set()

    for child in children:
        if child.get("kind") != "t3":
            continue
        post = child.get("data") or {}

        # Use permalink as canonical URL for the discussion thread
        permalink = post.get("permalink") or ""
        url = f"https://reddit.com{permalink}" if permalink else (post.get("url") or "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        title = post.get("title") or "Untitled"
        subreddit = post.get("subreddit") or "reddit"
        source = f"r/{subreddit}"
        created_utc = post.get("created_utc")
        published_date = _unix_to_iso(created_utc)

        # Use selftext if available, otherwise fall back to title
        selftext = (post.get("selftext") or "").strip()
        snippet = selftext[:300] if selftext else title

        articles.append(
            NormalizedArticle(
                title=title,
                url=url,
                source=source,
                published_date=published_date,
                snippet=snippet,
                thumbnail_url=None,
            )
        )

    return NormalizedResponse(
        articles=articles,
        query=query,
        total_results=len(articles),
        cached=False,
        request_id=request_id,
    )


async def execute_search_reddit(
    query: str,
    subreddit: str | None = None,
    num_results: int = 10,
    *,
    cache: ResponseCache,
    rate_limiter: RateLimiter,
) -> dict[str, Any]:
    """Search Reddit posts for a query.

    Parameters
    ----------
    query:
        The search query string (max 200 characters).
    subreddit:
        Optional subreddit to restrict the search to (e.g. ``"MachineLearning"``).
    num_results:
        Number of results to return (1–50). Defaults to 10.
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
    errors = validate_search_reddit_inputs(query, subreddit, num_results)
    if errors:
        return validation_error_response(errors)

    # 2. Check cache.
    cache_key = ResponseCache.make_key(
        "search_reddit",
        {"query": query, "subreddit": subreddit, "num_results": num_results},
    )
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        logger.info("Cache HIT — search_reddit query=%r", query)
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

    # 4. Call Reddit JSON API.
    if subreddit:
        url = _REDDIT_SUBREDDIT_URL.format(subreddit=subreddit)
        params: dict[str, str] = {
            "q": query,
            "restrict_sr": "1",
            "sort": "relevance",
            "limit": str(min(num_results, 50)),
            "t": "all",
        }
    else:
        url = _REDDIT_SEARCH_URL
        params = {
            "q": query,
            "sort": "relevance",
            "limit": str(min(num_results, 50)),
            "t": "all",
        }

    try:
        async with httpx.AsyncClient(timeout=_REDDIT_TIMEOUT) as http:
            response = await http.get(url, params=params, headers=_REDDIT_HEADERS)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
    except httpx.TimeoutException as exc:
        return upstream_timeout_response(exc, request_id)
    except httpx.HTTPStatusError as exc:
        return upstream_error_response(exc, request_id)
    except httpx.HTTPError as exc:
        logger.error("UPSTREAM_ERROR: Reddit httpx error — %s", exc)
        from src.middleware.error_handler import ErrorDetail, ErrorResponse
        resp = ErrorResponse(
            error=ErrorDetail(
                code="UPSTREAM_ERROR",
                message=f"HTTP error contacting Reddit API: {type(exc).__name__}",
                details={"exception_type": type(exc).__name__, "request_id": request_id},
            )
        )
        return resp.model_dump()
    except Exception as exc:
        return internal_error_response(exc, request_id)

    # 5. Normalise.
    try:
        normalised = _normalize_reddit_response(data, query=query, request_id=request_id)
    except Exception as exc:
        return internal_error_response(exc, request_id)

    # 6. Store in cache.
    result = normalised.model_dump()
    cache.set(cache_key, result)

    logger.info(
        "search_reddit OK — query=%r subreddit=%r results=%d request_id=%s",
        query,
        subreddit,
        normalised.total_results,
        request_id,
    )
    return result
