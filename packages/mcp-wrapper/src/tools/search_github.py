"""``search_github`` MCP tool implementation.

Searches GitHub repositories using the GitHub REST Search API (no API key
required for public repos, though rate limits apply).  Returns a normalised
list of repository results.

Middleware pipeline
-------------------
1. Validate inputs.
2. Check cache (return cached response if hit).
3. Check rate limit.
4. Call GitHub REST API directly (no SerpApi).
5. Normalise repository results to NormalizedResponse.
6. Store in cache.
7. Return normalised response.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

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
from src.middleware.validator import validate_search_github_inputs
from src.serpapi.models import NormalizedArticle, NormalizedResponse

logger = logging.getLogger(__name__)

_GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
_GITHUB_TIMEOUT = 10.0
_GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "SignalOps/1.0",
}


def _normalize_github_response(
    data: dict[str, Any],
    query: str,
    request_id: str,
) -> NormalizedResponse:
    """Convert a GitHub repository search response to NormalizedResponse."""
    items: list[dict[str, Any]] = data.get("items") or []
    articles: list[NormalizedArticle] = []
    seen_urls: set[str] = set()

    for repo in items:
        url = repo.get("html_url") or ""
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        full_name = repo.get("full_name") or "Unknown"
        description = repo.get("description") or "No description"
        stars = repo.get("stargazers_count", 0)
        language = repo.get("language") or "Unknown language"
        updated_at = repo.get("updated_at") or datetime.now(tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        snippet = f"{description} | ⭐ {stars:,} stars | {language}"

        articles.append(
            NormalizedArticle(
                title=full_name,
                url=url,
                source="GitHub",
                published_date=updated_at,
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


async def execute_search_github(
    query: str,
    num_results: int = 10,
    *,
    cache: ResponseCache,
    rate_limiter: RateLimiter,
) -> dict[str, Any]:
    """Search GitHub repositories for a query.

    Parameters
    ----------
    query:
        The search query string (max 200 characters).
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
    errors = validate_search_github_inputs(query, num_results)
    if errors:
        return validation_error_response(errors)

    # 2. Check cache.
    cache_key = ResponseCache.make_key(
        "search_github",
        {"query": query, "num_results": num_results},
    )
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        logger.info("Cache HIT — search_github query=%r", query)
        cached_value["cached"] = True
        cached_value["request_id"] = request_id
        return cached_value

    # 3. Rate limit check (uses same shared limiter to guard total API budget).
    limit_error = rate_limiter.check()
    if limit_error:
        return rate_limit_error_response(
            limit_error.retry_after_seconds,
            limit_error.limit_type,
        )

    # 4. Call GitHub REST API directly.
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": str(min(num_results, 50)),
    }
    try:
        async with httpx.AsyncClient(timeout=_GITHUB_TIMEOUT) as http:
            response = await http.get(
                _GITHUB_SEARCH_URL,
                params=params,
                headers=_GITHUB_HEADERS,
            )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
    except httpx.TimeoutException as exc:
        return upstream_timeout_response(exc, request_id)
    except httpx.HTTPStatusError as exc:
        return upstream_error_response(exc, request_id)
    except httpx.HTTPError as exc:
        logger.error("UPSTREAM_ERROR: GitHub httpx error — %s", exc)
        from src.middleware.error_handler import ErrorDetail, ErrorResponse
        resp = ErrorResponse(
            error=ErrorDetail(
                code="UPSTREAM_ERROR",
                message=f"HTTP error contacting GitHub API: {type(exc).__name__}",
                details={"exception_type": type(exc).__name__, "request_id": request_id},
            )
        )
        return resp.model_dump()
    except Exception as exc:
        return internal_error_response(exc, request_id)

    # 5. Normalise.
    try:
        normalised = _normalize_github_response(data, query=query, request_id=request_id)
    except Exception as exc:
        return internal_error_response(exc, request_id)

    # 6. Store in cache.
    result = normalised.model_dump()
    cache.set(cache_key, result)

    logger.info(
        "search_github OK — query=%r results=%d request_id=%s",
        query,
        normalised.total_results,
        request_id,
    )
    return result
