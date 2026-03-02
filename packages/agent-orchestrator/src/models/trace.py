"""Tool trace models for audit logging and the traceability store."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ToolTraceEntry(BaseModel):
    """Record of a single MCP tool call made during digest generation."""

    tool_name: str
    input: dict[str, object]
    output_summary: str
    latency_ms: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: str = "success"
    error: str | None = None


class ReportTrace(BaseModel):
    """Full trace for a digest report (sent to Traceability Store)."""

    report_id: str
    digest_type: str
    query: str
    generated_at: datetime
    tool_calls: list[ToolTraceEntry]
    total_articles_fetched: int
    total_articles_used: int
