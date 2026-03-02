"""Pydantic request and response models for the Traceability Store API.

All timestamps are in ISO 8601 UTC format. JSONB fields are represented as
``dict[str, Any]`` or ``Any`` to allow any valid JSON structure.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------


class _CamelBase(BaseModel):
    """Base model with alias generator disabled (snake_case throughout)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ---------------------------------------------------------------------------
# Report schemas
# ---------------------------------------------------------------------------

DigestType = Literal["daily_digest", "weekly_report", "risk_alert", "competitor_monitor"]


class CreateReportRequest(_CamelBase):
    """Payload sent by the Agent Orchestrator to persist a new digest report.

    Attributes:
        report_id: Human-readable report identifier (e.g., ``rpt_abc123``).
        digest_type: Classified intent of the digest.
        query: Original natural-language prompt from the user.
        digest_json: Full structured digest as a JSON object.
        generated_at: UTC timestamp of when the digest was generated.
        user_id: Optional user identifier for future multi-user support.
    """

    report_id: str = Field(..., min_length=1, max_length=50, examples=["rpt_abc123"])
    digest_type: DigestType
    query: str = Field(..., min_length=1)
    digest_json: dict[str, Any]
    generated_at: datetime
    user_id: str | None = Field(default=None, max_length=100)


class ReportSummaryResponse(_CamelBase):
    """Lightweight report representation returned in list responses.

    The ``digest_json`` field is intentionally omitted to keep list payloads
    small. Fetch the full report via ``GET /api/reports/{report_id}``.
    """

    id: uuid.UUID
    report_id: str
    digest_type: str
    query: str
    user_id: str | None
    generated_at: datetime
    created_at: datetime


class ReportDetailResponse(_CamelBase):
    """Full report representation including the complete ``digest_json``."""

    id: uuid.UUID
    report_id: str
    digest_type: str
    query: str
    digest_json: dict[str, Any]
    user_id: str | None
    generated_at: datetime
    created_at: datetime


class PaginatedReportsResponse(_CamelBase):
    """Paginated list of report summaries.

    Attributes:
        items: Current page of report summaries.
        total: Total number of matching reports (for UI pagination controls).
        limit: Page size used for this response.
        offset: Number of records skipped.
    """

    items: list[ReportSummaryResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Tool call schemas
# ---------------------------------------------------------------------------

ToolCallStatus = Literal["success", "error", "timeout"]


class CreateToolCallRequest(_CamelBase):
    """Payload for logging a single MCP tool call against a report.

    Attributes:
        tool_name: Name of the MCP tool invoked (e.g., ``search_news``).
        input_json: Input parameters passed to the tool.
        output_json: Tool output; ``None`` when the call failed.
        latency_ms: Wall-clock execution time in milliseconds.
        status: Outcome of the call.
        error_message: Details when ``status`` is ``error`` or ``timeout``.
        timestamp: UTC time when the tool was invoked.
    """

    tool_name: str = Field(..., min_length=1, max_length=100)
    input_json: dict[str, Any]
    output_json: dict[str, Any] | None = None
    latency_ms: int = Field(..., ge=0)
    status: ToolCallStatus
    error_message: str | None = None
    timestamp: datetime


class ToolCallResponse(_CamelBase):
    """Representation of a stored tool call, including its database ID."""

    id: uuid.UUID
    report_id: str
    tool_name: str
    input_json: dict[str, Any]
    output_json: dict[str, Any] | None
    latency_ms: int
    status: str
    error_message: str | None
    timestamp: datetime
    created_at: datetime


# ---------------------------------------------------------------------------
# Source schemas
# ---------------------------------------------------------------------------


class SourceItem(_CamelBase):
    """A single source article to be recorded for a report.

    Attributes:
        url: Article URL (no length limit; may be a long URL).
        title: Article title.
        source_name: Publisher name (e.g., ``TechCrunch``).
        published_date: UTC publication date of the article.
        snippet: Short excerpt used to verify relevance.
        accessed_at: UTC time when the article was fetched by the MCP Wrapper.
    """

    url: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    source_name: str | None = None
    published_date: datetime | None = None
    snippet: str | None = None
    accessed_at: datetime


class CreateSourcesRequest(_CamelBase):
    """Payload for bulk-inserting sources for a report.

    Attributes:
        sources: One or more source articles to record.
    """

    sources: list[SourceItem] = Field(..., min_length=1)


class SourceResponse(_CamelBase):
    """Representation of a stored source article."""

    id: uuid.UUID
    report_id: str
    url: str
    title: str
    source_name: str | None
    published_date: datetime | None
    snippet: str | None
    accessed_at: datetime
    created_at: datetime


# ---------------------------------------------------------------------------
# Metrics schemas
# ---------------------------------------------------------------------------


class ToolLatencyResponse(_CamelBase):
    """Latency percentile statistics for successful tool calls.

    All values are in milliseconds. ``None`` indicates no data was found
    for the given filters (no successful calls in the window).
    """

    p50_ms: int | None
    p95_ms: int | None
    p99_ms: int | None
    avg_ms: int | None
    count: int


class ToolErrorStat(_CamelBase):
    """Per-tool error rate breakdown."""

    tool_name: str
    total: int
    errors: int
    error_rate: float


class ErrorRateResponse(_CamelBase):
    """Aggregate and per-tool error rate metrics.

    Attributes:
        total: Total tool calls in the query window.
        errors: Total non-success calls.
        error_rate: ``errors / total`` rounded to 4 decimal places.
        by_tool: Per-tool breakdown.
    """

    total: int
    errors: int
    error_rate: float
    by_tool: list[ToolErrorStat]


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class HealthResponse(_CamelBase):
    """Health check response.

    Attributes:
        status: ``"healthy"`` when everything is OK, ``"unhealthy"`` otherwise.
        db_connected: Whether the database is reachable.
    """

    status: Literal["healthy", "unhealthy"]
    db_connected: bool


# ---------------------------------------------------------------------------
# Error response (matches shared project convention)
# ---------------------------------------------------------------------------


class ErrorDetail(_CamelBase):
    """Structured error payload returned for 4xx / 5xx responses."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    retry_after_seconds: int | None = None


class ErrorResponse(_CamelBase):
    """Wrapper that matches the shared project error envelope."""

    error: ErrorDetail
