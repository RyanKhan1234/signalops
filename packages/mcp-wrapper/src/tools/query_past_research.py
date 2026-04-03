"""``query_past_research`` MCP tool — cross-session memory via traceability store.

Queries the Traceability Store for past digest reports matching a topic.
This demonstrates that the agent system has memory across sessions --
it can reference previous research to build on prior findings.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from src.middleware.cache import ResponseCache
from src.middleware.rate_limiter import RateLimiter
from src.serpapi.models import NormalizedArticle, NormalizedResponse

logger = logging.getLogger(__name__)

_TRACE_STORE_URL = os.getenv(
    "TRACEABILITY_STORE_URL", "http://traceability-store:8002"
).rstrip("/")
_TIMEOUT = 8.0


async def execute_query_past_research(
    query: str,
    *,
    cache: ResponseCache,
    rate_limiter: RateLimiter,
) -> dict[str, Any]:
    """Search past digest reports for related research.

    Parameters
    ----------
    query:
        Topic or keyword to search for in past digests.
    """
    request_id = str(uuid.uuid4())

    if not query or not query.strip():
        from src.middleware.error_handler import validation_error_response
        return validation_error_response([("query", "Query is required")])

    articles: list[NormalizedArticle] = []
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_TRACE_STORE_URL}/api/reports",
                params={"limit": 20, "offset": 0},
            )
            resp.raise_for_status()
            data = resp.json()

        reports = data.get("items", [])

        query_lower = query.lower()
        query_terms = set(query_lower.split())

        matched: list[dict[str, Any]] = []
        for report in reports:
            report_query = (report.get("query") or "").lower()
            report_type = report.get("digest_type", "")
            score = 0
            for term in query_terms:
                if term in report_query:
                    score += 2
            if report_type:
                for term in query_terms:
                    if term in report_type:
                        score += 1
            if score > 0:
                matched.append({**report, "_relevance": score})

        matched.sort(key=lambda r: r["_relevance"], reverse=True)

        for report in matched[:8]:
            generated = report.get("generated_at", now)
            articles.append(
                NormalizedArticle(
                    title=f"Past Research: {report.get('query', 'Unknown')}",
                    url=f"signalops://reports/{report.get('report_id', 'unknown')}",
                    source=f"SignalOps Archive ({report.get('digest_type', 'unknown')})",
                    published_date=str(generated),
                    snippet=(
                        f"Digest type: {report.get('digest_type', 'N/A')}\n"
                        f"Query: {report.get('query', 'N/A')}\n"
                        f"Report ID: {report.get('report_id', 'N/A')}\n"
                        f"Generated: {generated}"
                    ),
                )
            )

        if not matched and reports:
            articles.append(
                NormalizedArticle(
                    title=f"No past research found matching '{query}'",
                    url=f"signalops://reports/none",
                    source="SignalOps Archive",
                    published_date=now,
                    snippet=(
                        f"Searched {len(reports)} past digest(s) but none matched "
                        f"'{query}'. Recent topics: "
                        + ", ".join(r.get("query", "?")[:50] for r in reports[:5])
                    ),
                )
            )

    except httpx.ConnectError:
        logger.warning("Traceability store unreachable at %s", _TRACE_STORE_URL)
        articles.append(
            NormalizedArticle(
                title="Past research unavailable — archive service offline",
                url=f"signalops://reports/error",
                source="SignalOps Archive",
                published_date=now,
                snippet="The traceability store is not reachable. Past research cannot be queried.",
            )
        )
    except Exception as exc:
        logger.error("query_past_research error: %s", exc)
        articles.append(
            NormalizedArticle(
                title=f"Past research query failed: {type(exc).__name__}",
                url=f"signalops://reports/error",
                source="SignalOps Archive",
                published_date=now,
                snippet=f"Error querying past research: {exc}",
            )
        )

    response = NormalizedResponse(
        articles=articles,
        query=query,
        total_results=len(articles),
        cached=False,
        request_id=request_id,
    )
    return response.model_dump()
