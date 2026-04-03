"""``fetch_page`` MCP tool implementation.

Fetches a web page and extracts its plain-text content, title, and metadata.
Uses httpx directly (no SerpApi). Returns a single-article NormalizedResponse
so the MCP client can handle it uniformly.

Middleware pipeline
-------------------
1. Validate URL input.
2. Check cache (1-hour TTL — page content is relatively stable).
3. Check rate limit.
4. Fetch URL with httpx.
5. Extract title and strip HTML to plain text.
6. Store in cache.
7. Return normalised response.
"""

from __future__ import annotations

import html
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

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
from src.middleware.validator import validate_fetch_page_inputs
from src.serpapi.models import NormalizedArticle, NormalizedResponse

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT = 15.0
_FETCH_HEADERS = {
    "User-Agent": "SignalOps/1.0 (research tool)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_MAX_TEXT_LENGTH = 5000
_TITLE_PATTERN = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_TAG_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s{2,}")


def _extract_title(raw_html: str) -> str:
    """Extract and clean the <title> tag content."""
    match = _TITLE_PATTERN.search(raw_html)
    if match:
        return html.unescape(_TAG_PATTERN.sub("", match.group(1))).strip()
    return ""


def _extract_text(raw_html: str) -> str:
    """Strip HTML tags and collapse whitespace to extract plain text."""
    # Remove script and style blocks entirely
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw_html, flags=re.IGNORECASE | re.DOTALL)
    # Strip remaining tags
    text = _TAG_PATTERN.sub(" ", cleaned)
    # Unescape HTML entities
    text = html.unescape(text)
    # Collapse whitespace
    text = _WHITESPACE_PATTERN.sub(" ", text).strip()
    return text[:_MAX_TEXT_LENGTH]


def _extract_domain(url: str) -> str:
    """Extract the domain from a URL."""
    try:
        return urlparse(url).netloc or url
    except Exception:
        return url


async def execute_fetch_page(
    url: str,
    *,
    cache: ResponseCache,
    rate_limiter: RateLimiter,
) -> dict[str, Any]:
    """Fetch a web page and return its plain-text content.

    Parameters
    ----------
    url:
        The full HTTP/HTTPS URL to fetch.
    cache:
        Injected ``ResponseCache`` instance (uses metadata TTL — 1 hour).
    rate_limiter:
        Injected ``RateLimiter`` instance.

    Returns
    -------
    dict
        Serialised ``NormalizedResponse`` with one article on success,
        or a structured error dict.
    """
    request_id = str(uuid.uuid4())

    # 1. Validate inputs.
    errors = validate_fetch_page_inputs(url)
    if errors:
        return validation_error_response(errors)

    # 2. Check cache.
    cache_key = ResponseCache.make_key("fetch_page", {"url": url})
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        logger.info("Cache HIT — fetch_page url=%r", url)
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

    # 4. Fetch the page.
    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT, follow_redirects=True) as http:
            response = await http.get(url, headers=_FETCH_HEADERS)
        response.raise_for_status()
        raw_html = response.text
    except httpx.TimeoutException as exc:
        return upstream_timeout_response(exc, request_id)
    except httpx.HTTPStatusError as exc:
        return upstream_error_response(exc, request_id)
    except httpx.HTTPError as exc:
        logger.error("UPSTREAM_ERROR: fetch_page httpx error — %s", exc)
        from src.middleware.error_handler import ErrorDetail, ErrorResponse
        resp = ErrorResponse(
            error=ErrorDetail(
                code="UPSTREAM_ERROR",
                message=f"HTTP error fetching page: {type(exc).__name__}",
                details={"exception_type": type(exc).__name__, "request_id": request_id, "url": url},
            )
        )
        return resp.model_dump()
    except Exception as exc:
        return internal_error_response(exc, request_id)

    # 5. Extract content.
    try:
        title = _extract_title(raw_html) or url
        text_content = _extract_text(raw_html)
        snippet = text_content[:1500]
        domain = _extract_domain(url)
        fetched_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception as exc:
        return internal_error_response(exc, request_id)

    normalised = NormalizedResponse(
        articles=[
            NormalizedArticle(
                title=title,
                url=url,
                source=domain,
                published_date=fetched_at,
                snippet=snippet,
                thumbnail_url=None,
            )
        ],
        query=url,
        total_results=1,
        cached=False,
        request_id=request_id,
    )

    # 6. Store in cache.
    result = normalised.model_dump()
    cache.set(cache_key, result)

    logger.info(
        "fetch_page OK — url=%r word_count=%d request_id=%s",
        url,
        len(text_content.split()),
        request_id,
    )
    return result
