"""Response normalizer for SerpApi results.

Transforms raw ``SerpApiResponse`` objects into the canonical
``NormalizedResponse`` schema used throughout SignalOps.

Key responsibilities
--------------------
* Parse relative dates ("2 hours ago", "3 days ago", "1 week ago") to ISO 8601.
* Strip HTML entities from titles and snippets.
* Deduplicate articles by URL within a single response.
* Generate a UUID ``request_id`` for each response (used for traceability).
"""

from __future__ import annotations

import html
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from src.serpapi.models import NormalizedArticle, NormalizedResponse, SerpApiResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Relative-date parsing
# ---------------------------------------------------------------------------

_RELATIVE_DATE_PATTERN = re.compile(
    r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago",
    re.IGNORECASE,
)

_UNIT_DELTAS: dict[str, timedelta] = {
    "second": timedelta(seconds=1),
    "minute": timedelta(minutes=1),
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(weeks=1),
    "month": timedelta(days=30),
    "year": timedelta(days=365),
}

# Common absolute date formats SerpApi sometimes returns.
_ABSOLUTE_DATE_FORMATS = [
    "%b %d, %Y",       # "Mar 01, 2026"
    "%B %d, %Y",       # "March 01, 2026"
    "%Y-%m-%dT%H:%M:%SZ",  # ISO 8601 already
    "%Y-%m-%d",        # "2026-03-01"
    "%m/%d/%Y",        # "03/01/2026"
]


def _parse_date(raw_date: str | None) -> str:
    """Parse a SerpApi date string to an ISO 8601 UTC string.

    Handles relative dates (e.g. "2 hours ago") and common absolute date
    formats.  Falls back to the current UTC time if parsing fails.

    Parameters
    ----------
    raw_date:
        The raw date string from SerpApi, or ``None``.

    Returns
    -------
    str
        An ISO 8601 UTC timestamp string (e.g. ``"2026-03-01T12:00:00Z"``).
    """
    if not raw_date:
        return _now_iso()

    # Try relative date first.
    match = _RELATIVE_DATE_PATTERN.search(raw_date)
    if match:
        quantity = int(match.group(1))
        unit = match.group(2).lower()
        delta = _UNIT_DELTAS[unit] * quantity
        dt = datetime.now(tz=timezone.utc) - delta
        return _to_iso(dt)

    # Try absolute date formats.
    clean = raw_date.strip()
    for fmt in _ABSOLUTE_DATE_FORMATS:
        try:
            dt = datetime.strptime(clean, fmt)
            # Assume UTC if no timezone info present.
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return _to_iso(dt)
        except ValueError:
            continue

    # Log unrecognised format and fall back to now.
    logger.warning("Could not parse date %r; defaulting to now", raw_date)
    return _now_iso()


def _to_iso(dt: datetime) -> str:
    """Format a ``datetime`` to an ISO 8601 UTC string ending with ``Z``."""
    utc = dt.astimezone(timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return _to_iso(datetime.now(tz=timezone.utc))


# ---------------------------------------------------------------------------
# HTML entity stripping
# ---------------------------------------------------------------------------


def _strip_html(text: str | None) -> str:
    """Unescape HTML entities and strip residual HTML tags from a string.

    Parameters
    ----------
    text:
        Raw text possibly containing HTML entities (``&amp;``, ``&#39;``…).

    Returns
    -------
    str
        Cleaned plain-text string.
    """
    if not text:
        return ""
    unescaped = html.unescape(text)
    # Remove any remaining HTML tags (e.g. <b>, <em>)
    clean = re.sub(r"<[^>]+>", "", unescaped)
    return clean.strip()


# ---------------------------------------------------------------------------
# Source extraction helper
# ---------------------------------------------------------------------------


def _extract_source(raw: dict[str, Any]) -> str:
    """Extract the human-readable source name from a SerpApi news result dict."""
    source_value = raw.get("source")
    if isinstance(source_value, dict):
        return _strip_html(source_value.get("name") or source_value.get("href") or "")
    if isinstance(source_value, str):
        return _strip_html(source_value)
    return "Unknown"


# ---------------------------------------------------------------------------
# Public normalizer
# ---------------------------------------------------------------------------


def normalize_response(
    raw: SerpApiResponse,
    query: str,
    cached: bool = False,
    request_id: str | None = None,
) -> NormalizedResponse:
    """Transform a raw ``SerpApiResponse`` into a ``NormalizedResponse``.

    Parameters
    ----------
    raw:
        The parsed (but un-normalised) SerpApi response.
    query:
        The original query string — stored on the response for traceability.
    cached:
        Whether this response came from the cache.
    request_id:
        UUID string to use as the request identifier.  A new UUID is generated
        if ``None`` is supplied.

    Returns
    -------
    NormalizedResponse
        The canonical SignalOps article list.
    """
    rid = request_id or str(uuid.uuid4())
    articles: list[NormalizedArticle] = []
    seen_urls: set[str] = set()

    raw_results = raw.news_results or raw.top_stories or []
    for item in raw_results:
        url = item.get("link") or ""
        if not url:
            continue  # Skip results without a URL.

        # Deduplicate by URL.
        normalised_url = url.strip().rstrip("/")
        if normalised_url in seen_urls:
            logger.debug("Deduplicating article with URL: %s", normalised_url)
            continue
        seen_urls.add(normalised_url)

        title = _strip_html(item.get("title"))
        snippet = _strip_html(item.get("snippet"))
        published_date = _parse_date(item.get("date"))
        source = _extract_source(item)
        thumbnail_url = item.get("thumbnail") or None

        articles.append(
            NormalizedArticle(
                title=title or "Untitled",
                url=normalised_url,
                source=source,
                published_date=published_date,
                snippet=snippet,
                thumbnail_url=thumbnail_url,
            )
        )

    return NormalizedResponse(
        articles=articles,
        query=query,
        total_results=len(articles),
        cached=cached,
        request_id=rid,
    )


def normalize_organic_results(
    raw: SerpApiResponse,
    query: str,
    cached: bool = False,
    request_id: str | None = None,
) -> NormalizedResponse:
    """Normalize ``organic_results`` from Google web, Scholar, or Quora searches.

    Used by ``search_web``, ``search_scholar``, and ``search_quora`` tools.
    Reads ``raw.model_extra["organic_results"]`` because ``SerpApiResponse``
    uses ``extra="allow"`` to capture engine-specific fields.

    Parameters
    ----------
    raw:
        The parsed (but un-normalised) SerpApi response.
    query:
        The original query string — stored on the response for traceability.
    cached:
        Whether this response came from the cache.
    request_id:
        UUID string to use as the request identifier.  A new UUID is generated
        if ``None`` is supplied.

    Returns
    -------
    NormalizedResponse
        The canonical SignalOps article list.
    """
    rid = request_id or str(uuid.uuid4())
    articles: list[NormalizedArticle] = []
    seen_urls: set[str] = set()

    raw_results: list[dict[str, Any]] = raw.model_extra.get("organic_results") or []
    for item in raw_results:
        url = item.get("link") or ""
        if not url:
            continue

        normalised_url = url.strip().rstrip("/")
        if normalised_url in seen_urls:
            logger.debug("Deduplicating organic result with URL: %s", normalised_url)
            continue
        seen_urls.add(normalised_url)

        title = _strip_html(item.get("title"))
        snippet = _strip_html(item.get("snippet"))
        published_date = _parse_date(item.get("date"))
        # organic_results carry source as a plain domain string (e.g. "techcrunch.com")
        source_raw = item.get("source")
        if isinstance(source_raw, str):
            source = _strip_html(source_raw) or "Unknown"
        else:
            source = "Unknown"
        thumbnail_url = item.get("thumbnail") or None

        articles.append(
            NormalizedArticle(
                title=title or "Untitled",
                url=normalised_url,
                source=source,
                published_date=published_date,
                snippet=snippet,
                thumbnail_url=thumbnail_url,
            )
        )

    return NormalizedResponse(
        articles=articles,
        query=query,
        total_results=len(articles),
        cached=cached,
        request_id=rid,
    )


def normalize_video_results(
    raw: SerpApiResponse,
    query: str,
    cached: bool = False,
    request_id: str | None = None,
) -> NormalizedResponse:
    """Normalize ``video_results`` from the YouTube engine.

    Reads ``raw.model_extra["video_results"]`` because ``SerpApiResponse``
    uses ``extra="allow"`` to capture engine-specific fields.

    Parameters
    ----------
    raw:
        The parsed (but un-normalised) SerpApi response.
    query:
        The original query string — stored on the response for traceability.
    cached:
        Whether this response came from the cache.
    request_id:
        UUID string to use as the request identifier.  A new UUID is generated
        if ``None`` is supplied.

    Returns
    -------
    NormalizedResponse
        The canonical SignalOps article list, one entry per video.
    """
    rid = request_id or str(uuid.uuid4())
    articles: list[NormalizedArticle] = []
    seen_urls: set[str] = set()

    raw_results: list[dict[str, Any]] = raw.model_extra.get("video_results") or []
    for item in raw_results:
        url = item.get("link") or ""
        if not url:
            continue

        normalised_url = url.strip().rstrip("/")
        if normalised_url in seen_urls:
            logger.debug("Deduplicating video result with URL: %s", normalised_url)
            continue
        seen_urls.add(normalised_url)

        title = _strip_html(item.get("title"))
        # description field maps to snippet
        snippet = _strip_html(item.get("description"))
        # channel.name is the source; fall back to "YouTube"
        channel = item.get("channel") or {}
        source = _strip_html(channel.get("name")) if isinstance(channel, dict) else ""
        source = source or "YouTube"
        published_date = _parse_date(item.get("published_date"))
        # thumbnail is nested: thumbnail.static
        thumbnail_raw = item.get("thumbnail")
        thumbnail_url: str | None = None
        if isinstance(thumbnail_raw, dict):
            thumbnail_url = thumbnail_raw.get("static") or None
        elif isinstance(thumbnail_raw, str):
            thumbnail_url = thumbnail_raw or None

        articles.append(
            NormalizedArticle(
                title=title or "Untitled",
                url=normalised_url,
                source=source,
                published_date=published_date,
                snippet=snippet,
                thumbnail_url=thumbnail_url,
            )
        )

    return NormalizedResponse(
        articles=articles,
        query=query,
        total_results=len(articles),
        cached=cached,
        request_id=rid,
    )
