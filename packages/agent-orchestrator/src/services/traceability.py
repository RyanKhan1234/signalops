"""Traceability Store client for the Agent Orchestrator.

Sends completed digest reports and individual tool call logs to the
Traceability Store service for audit, compliance, and performance monitoring.

All calls are fire-and-forget where possible; traceability failures must never
block digest delivery to the user.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from src.config import settings
from src.models.digest import DigestResponse
from src.models.trace import ReportTrace, ToolTraceEntry

logger = logging.getLogger(__name__)

# Timeout for traceability calls (seconds) — short because these are non-blocking
TRACE_TIMEOUT = 10.0


class TraceabilityClient:
    """Async client for logging digests and tool calls to the Traceability Store."""

    def __init__(
        self,
        base_url: str = settings.traceability_store_url,
        correlation_id: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._correlation_id = correlation_id

    async def log_report(self, report: DigestResponse) -> None:
        """Log a completed digest report to the Traceability Store.

        Sends the full digest JSON plus a structured report trace.
        This call is best-effort — failures are logged but do not raise.

        Args:
            report: The final validated DigestResponse.
        """
        trace = ReportTrace(
            report_id=report.report_id,
            digest_type=report.digest_type,
            query=report.query,
            generated_at=report.generated_at,
            tool_calls=report.tool_trace,
            total_articles_fetched=len(report.sources),
            total_articles_used=len(report.sources),
        )

        payload = {
            "report_id": report.report_id,
            "digest_type": report.digest_type,
            "query": report.query,
            "generated_at": report.generated_at.isoformat(),
            "digest_json": report.model_dump(mode="json"),
            "tool_trace": trace.model_dump(mode="json"),
        }

        await self._post("/reports", payload)

    async def log_tool_call(self, call: ToolTraceEntry, report_id: str) -> None:
        """Log an individual tool call to the Traceability Store.

        Args:
            call: The tool call trace entry.
            report_id: The parent report ID for this tool call.
        """
        payload = {
            "report_id": report_id,
            "tool_name": call.tool_name,
            "input_json": call.input,
            "output_summary": call.output_summary,
            "latency_ms": call.latency_ms,
            "timestamp": call.timestamp.isoformat() if call.timestamp else datetime.now(tz=timezone.utc).isoformat(),
            "status": call.status,
            "error": call.error,
        }

        await self._post("/tool-calls", payload)

    async def _post(self, path: str, payload: dict[str, object]) -> None:
        """POST a payload to the Traceability Store. Best-effort, never raises."""
        url = f"{self._base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self._correlation_id:
            headers[settings.correlation_id_header] = self._correlation_id

        try:
            async with httpx.AsyncClient(timeout=TRACE_TIMEOUT) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code not in (200, 201, 202):
                    logger.warning(
                        "Traceability Store returned HTTP %d for %s: %s",
                        response.status_code,
                        path,
                        response.text[:200],
                    )
                else:
                    logger.debug("Traceability logged to %s (HTTP %d)", path, response.status_code)
        except httpx.ConnectError:
            logger.warning(
                "Traceability Store unreachable at %s — skipping trace log for %s",
                self._base_url,
                path,
            )
        except httpx.TimeoutException:
            logger.warning("Traceability Store timed out for %s — skipping", path)
        except Exception as exc:
            logger.error("Unexpected traceability error for %s: %s", path, exc)
