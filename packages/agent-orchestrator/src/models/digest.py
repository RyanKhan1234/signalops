"""Digest data models for the Agent Orchestrator pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Article / Source models (returned by MCP Wrapper)
# ---------------------------------------------------------------------------


class Article(BaseModel):
    """Normalized article returned by the MCP Wrapper."""

    title: str
    url: str
    source: str
    published_date: str
    snippet: str
    thumbnail_url: str | None = None


class MCPToolResult(BaseModel):
    """Normalized response from an MCP tool call."""

    articles: list[Article]
    query: str
    total_results: int
    cached: bool
    request_id: str


# ---------------------------------------------------------------------------
# Intent models
# ---------------------------------------------------------------------------

DigestType = Literal["daily_digest", "weekly_report", "risk_alert", "competitor_monitor"]


class DetectedIntent(BaseModel):
    """Structured intent extracted from a user prompt."""

    intent_type: DigestType
    entities: list[str] = Field(description="Company names, topics, or threat vectors")
    time_range: str = Field(description="Time range code, e.g. '1d', '7d', '30d'")
    original_query: str


# ---------------------------------------------------------------------------
# Planned tool call models
# ---------------------------------------------------------------------------


class PlannedToolCall(BaseModel):
    """A single planned MCP tool call."""

    tool_name: Literal["search_news", "search_company_news", "get_article_metadata"]
    arguments: dict[str, str | list[str] | int]
    parallel_group: int = Field(
        default=0,
        description="Calls with the same group number can be executed in parallel",
    )


class ToolPlan(BaseModel):
    """Ordered plan of MCP tool calls derived from a detected intent."""

    intent: DetectedIntent
    calls: list[PlannedToolCall]


# ---------------------------------------------------------------------------
# Processed article pipeline models
# ---------------------------------------------------------------------------


class ArticleCluster(BaseModel):
    """A cluster of articles grouped by topic/theme."""

    theme: str
    articles: list[Article]


class KeySignal(BaseModel):
    """A key signal extracted from an article cluster."""

    signal: str
    source_url: str
    source_title: str
    published_date: str
    relevance: Literal["high", "medium", "low"]


class Risk(BaseModel):
    """An identified competitive risk."""

    description: str
    severity: Literal["high", "medium", "low"]
    source_urls: list[str]


class Opportunity(BaseModel):
    """An identified strategic opportunity."""

    description: str
    confidence: Literal["high", "medium", "low"]
    source_urls: list[str]


class ActionItem(BaseModel):
    """A prioritized action item for the ops team."""

    action: str
    priority: Literal["P0", "P1", "P2"]
    rationale: str


class Source(BaseModel):
    """A source article referenced in the digest."""

    url: str
    title: str
    published_date: str
    snippet: str


# ---------------------------------------------------------------------------
# Final digest response
# ---------------------------------------------------------------------------


class DigestResponse(BaseModel):
    """The final structured digest returned to the Web App."""

    digest_type: DigestType
    query: str
    generated_at: datetime
    report_id: str
    executive_summary: str
    key_signals: list[KeySignal] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    opportunities: list[Opportunity] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    tool_trace: list["ToolTraceEntry"] = Field(default_factory=list)


# Avoid circular import — import ToolTraceEntry from trace module at model resolution time
from src.models.trace import ToolTraceEntry  # noqa: E402

DigestResponse.model_rebuild()
