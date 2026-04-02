"""API route definitions for the Agent Orchestrator FastAPI application."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, Response

from src.agent.orchestrator import run_pipeline
from src.api.schemas import DigestRequest, ErrorDetail, ErrorResponse, HealthResponse
from src.config import settings
from src.models.digest import DigestResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns a simple ok status. Used by load balancers and monitoring tools.
    """
    return HealthResponse()


@router.post(
    "/digest",
    response_model=DigestResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Pipeline error"},
        503: {"model": ErrorResponse, "description": "Upstream service unavailable"},
    },
    tags=["Digest"],
)
async def create_digest(
    body: DigestRequest,
    request: Request,
    response: Response,
) -> DigestResponse:
    """Generate a structured research digest from a natural language prompt.

    The pipeline:
    1. Detects intent (latest_news, deep_dive, risk_scan, trend_watch)
    2. Plans MCP tool calls
    3. Executes tool calls against the MCP Wrapper
    4. Processes articles: dedup → cluster → extract signals → identify risks/opps
    5. Composes and validates the structured digest
    6. Logs the tool trace to the Traceability Store
    7. Returns the validated digest JSON

    Args:
        body: DigestRequest with the user prompt.
        request: FastAPI request (for correlation ID extraction).
        response: FastAPI response (for setting response headers).

    Returns:
        DigestResponse with the full structured digest.
    """
    # Extract or generate correlation ID
    correlation_id = request.headers.get(settings.correlation_id_header, str(uuid.uuid4()))
    response.headers[settings.correlation_id_header] = correlation_id

    logger.info(
        "POST /digest correlation_id=%s prompt='%s'",
        correlation_id,
        body.prompt[:80],
    )

    try:
        digest = await run_pipeline(prompt=body.prompt, correlation_id=correlation_id)
        return digest

    except RuntimeError as exc:
        error_message = str(exc)
        logger.error(
            "Pipeline RuntimeError correlation_id=%s: %s",
            correlation_id,
            error_message,
        )

        # Detect upstream service errors
        if "Tool execution failed" in error_message or "MCP" in error_message:
            raise HTTPException(
                status_code=503,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code="UPSTREAM_UNAVAILABLE",
                        message="The MCP Wrapper service is unavailable. Please try again later.",
                        details={"correlation_id": correlation_id},
                        retry_after_seconds=30,
                    )
                ).model_dump(),
            ) from exc

        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="PIPELINE_ERROR",
                    message="An internal error occurred during digest generation.",
                    details={"correlation_id": correlation_id},
                )
            ).model_dump(),
        ) from exc

    except Exception as exc:
        logger.exception(
            "Unexpected error in POST /digest correlation_id=%s: %s",
            correlation_id,
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="An unexpected internal error occurred.",
                    details={"correlation_id": correlation_id},
                )
            ).model_dump(),
        ) from exc
