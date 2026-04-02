"""Pydantic request/response schemas for the FastAPI API layer."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DigestRequest(BaseModel):
    """Request body for POST /digest."""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language research prompt — any topic, company, or question",
        examples=["What's new in AI model releases this week?"],
    )


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str = "ok"
    version: str = "0.1.0"
    service: str = "agent-orchestrator"


class ErrorDetail(BaseModel):
    """Standard error detail object."""

    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)
    retry_after_seconds: int | None = None


class ErrorResponse(BaseModel):
    """Standard error response matching the shared error format."""

    error: ErrorDetail
