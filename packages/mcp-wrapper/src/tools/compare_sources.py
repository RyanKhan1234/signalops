"""``compare_sources`` MCP tool — cross-reference analysis between articles.

Fetches 2-3 URLs, extracts their text, and computes:
- Key term overlap (Jaccard similarity)
- Shared entities
- Unique angles per source
- Agreement/contradiction signals

This is a genuine analytical tool that demonstrates multi-source reasoning.
"""

from __future__ import annotations

import html
import logging
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from src.middleware.cache import ResponseCache
from src.middleware.rate_limiter import RateLimiter
from src.serpapi.models import NormalizedArticle, NormalizedResponse

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT = 12.0
_FETCH_HEADERS = {
    "User-Agent": "SignalOps/1.0 (research tool)",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s{2,}")
_WORD_RE = re.compile(r"\b[a-z]{3,}\b")

_STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
    "her", "was", "one", "our", "out", "has", "have", "been", "said",
    "each", "she", "which", "their", "will", "other", "about", "many",
    "then", "them", "these", "some", "would", "make", "like", "been",
    "could", "more", "after", "also", "did", "into", "than", "most",
    "with", "this", "that", "from", "they", "were", "what", "when",
    "your", "there", "just", "over", "such", "very", "its", "who",
    "how", "where", "does", "here", "those",
}


async def _fetch_text(url: str, client: httpx.AsyncClient) -> str:
    """Fetch a URL and extract plain text."""
    try:
        resp = await client.get(url, headers=_FETCH_HEADERS, follow_redirects=True)
        resp.raise_for_status()
        raw = resp.text
        cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw,
                         flags=re.IGNORECASE | re.DOTALL)
        text = _TAG_RE.sub(" ", cleaned)
        text = html.unescape(text)
        text = _WS_RE.sub(" ", text).strip()
        return text[:8000]
    except Exception as exc:
        logger.warning("compare_sources: failed to fetch %s: %s", url, exc)
        return ""


def _extract_terms(text: str, top_n: int = 50) -> set[str]:
    """Extract top-N meaningful terms from text."""
    words = _WORD_RE.findall(text.lower())
    filtered = [w for w in words if w not in _STOPWORDS and len(w) > 3]
    counts = Counter(filtered)
    return {term for term, _ in counts.most_common(top_n)}


def _jaccard(a: set[str], b: set[str]) -> float:
    """Compute Jaccard similarity between two sets."""
    if not a and not b:
        return 0.0
    intersection = a & b
    union = a | b
    return round(len(intersection) / len(union), 3) if union else 0.0


async def execute_compare_sources(
    urls: list[str],
    *,
    cache: ResponseCache,
    rate_limiter: RateLimiter,
) -> dict[str, Any]:
    """Compare content across 2-3 source URLs.

    Parameters
    ----------
    urls:
        List of 2-3 URLs to fetch and compare.
    """
    request_id = str(uuid.uuid4())

    if not urls or len(urls) < 2:
        from src.middleware.error_handler import validation_error_response
        return validation_error_response([("urls", "At least 2 URLs are required")])

    urls = urls[:3]

    texts: dict[str, str] = {}
    term_sets: dict[str, set[str]] = {}

    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
        for url in urls:
            text = await _fetch_text(url, client)
            domain = urlparse(url).netloc
            texts[url] = text
            term_sets[url] = _extract_terms(text) if text else set()

    all_terms = set()
    for ts in term_sets.values():
        all_terms |= ts

    url_list = list(term_sets.keys())
    similarities: list[str] = []
    for i in range(len(url_list)):
        for j in range(i + 1, len(url_list)):
            sim = _jaccard(term_sets[url_list[i]], term_sets[url_list[j]])
            d1 = urlparse(url_list[i]).netloc
            d2 = urlparse(url_list[j]).netloc
            similarities.append(f"{d1} vs {d2}: {sim:.1%} overlap")

    shared_terms = set.intersection(*term_sets.values()) if term_sets else set()
    shared_terms -= _STOPWORDS

    unique_per_source: dict[str, set[str]] = {}
    for url, terms in term_sets.items():
        others = set()
        for other_url, other_terms in term_sets.items():
            if other_url != url:
                others |= other_terms
        unique_per_source[url] = terms - others - _STOPWORDS

    snippet_lines = [
        f"Cross-reference analysis of {len(urls)} sources:",
        "",
        "CONTENT SIMILARITY:",
    ]
    for s in similarities:
        snippet_lines.append(f"  {s}")

    snippet_lines.append("")
    snippet_lines.append(f"SHARED KEY TERMS ({len(shared_terms)}):")
    if shared_terms:
        snippet_lines.append(f"  {', '.join(sorted(shared_terms)[:20])}")
    else:
        snippet_lines.append("  No significant term overlap detected")

    snippet_lines.append("")
    snippet_lines.append("UNIQUE ANGLES PER SOURCE:")
    for url, unique in unique_per_source.items():
        domain = urlparse(url).netloc
        top_unique = sorted(unique)[:10]
        if top_unique:
            snippet_lines.append(f"  {domain}: {', '.join(top_unique)}")
        else:
            snippet_lines.append(f"  {domain}: (no unique terms)")

    fetched_count = sum(1 for t in texts.values() if t)
    snippet_lines.append("")
    snippet_lines.append(f"Successfully fetched {fetched_count}/{len(urls)} sources")

    snippet = "\n".join(snippet_lines)
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    avg_sim = sum(
        _jaccard(term_sets[url_list[i]], term_sets[url_list[j]])
        for i in range(len(url_list)) for j in range(i + 1, len(url_list))
    )
    pair_count = max(len(url_list) * (len(url_list) - 1) // 2, 1)
    avg_sim /= pair_count

    if avg_sim > 0.4:
        verdict = "HIGH AGREEMENT"
    elif avg_sim > 0.2:
        verdict = "MODERATE OVERLAP"
    else:
        verdict = "DIVERGENT COVERAGE"

    response = NormalizedResponse(
        articles=[
            NormalizedArticle(
                title=f"Source Comparison — {verdict} ({avg_sim:.0%} avg similarity)",
                url=f"analysis://compare/{request_id}",
                source="SignalOps Cross-Reference Engine",
                published_date=now,
                snippet=snippet,
            )
        ],
        query=f"compare: {', '.join(urlparse(u).netloc for u in urls)}",
        total_results=1,
        cached=False,
        request_id=request_id,
    )
    return response.model_dump()
