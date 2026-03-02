"""Pydantic models for raw SerpApi responses.

These models represent the *raw* structure returned by SerpApi.  They are
intentionally permissive (most fields are optional) because SerpApi's
response shape varies across engines and query types.  The normalizer is
responsible for mapping these into the strict ``NormalizedArticle`` schema.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SerpApiNewsResult(BaseModel):
    """A single news article as returned by SerpApi's ``news_results`` array."""

    title: str | None = None
    link: str | None = None
    source: str | None = None
    date: str | None = None
    snippet: str | None = None
    thumbnail: str | None = None

    # SerpApi sometimes nests source info under a ``source`` object
    # rather than a plain string — capture both shapes.
    source_info: dict[str, Any] | None = Field(default=None, alias="source")

    model_config = {"populate_by_name": True, "extra": "allow"}


class SerpApiSearchInformation(BaseModel):
    """Top-level search metadata from SerpApi."""

    total_results: str | None = None
    time_taken_displayed: float | None = None
    query_displayed: str | None = None

    model_config = {"extra": "allow"}


class SerpApiError(BaseModel):
    """Error block returned by SerpApi on failure."""

    error: str


class SerpApiResponse(BaseModel):
    """Top-level SerpApi response envelope."""

    search_parameters: dict[str, Any] | None = None
    search_information: SerpApiSearchInformation | None = None
    news_results: list[dict[str, Any]] | None = None
    error: str | None = None

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Normalised output models (shared between normalizer and tools)
# ---------------------------------------------------------------------------


class NormalizedArticle(BaseModel):
    """A single article in the standardised SignalOps schema."""

    title: str
    url: str
    source: str
    published_date: str  # ISO 8601 UTC
    snippet: str
    thumbnail_url: str | None = None


class NormalizedResponse(BaseModel):
    """Complete normalised response returned by every MCP tool."""

    articles: list[NormalizedArticle]
    query: str
    total_results: int
    cached: bool = False
    request_id: str  # UUID for traceability
