"""API route definitions for the Agent Orchestrator FastAPI application."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

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
        digest = await run_pipeline(
            prompt=body.prompt,
            correlation_id=correlation_id,
            user_id=body.user_id,
        )
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


@router.post(
    "/digest/stream",
    tags=["Digest"],
    summary="Generate a digest with real-time SSE progress events",
)
async def create_digest_stream(
    body: DigestRequest,
    request: Request,
) -> StreamingResponse:
    """Generate a structured research digest with real-time streaming updates.

    Returns a Server-Sent Events stream with progress events as the pipeline
    runs, ending with a ``complete`` event containing the full digest.
    """
    correlation_id = request.headers.get(settings.correlation_id_header, str(uuid.uuid4()))

    logger.info(
        "POST /digest/stream correlation_id=%s prompt='%s'",
        correlation_id,
        body.prompt[:80],
    )

    event_queue: asyncio.Queue[dict | None] = asyncio.Queue()

    def on_event(event_type: str, data: dict) -> None:
        event_queue.put_nowait({"event": event_type, "data": data})

    async def event_generator():
        pipeline_task = asyncio.create_task(
            run_pipeline(
                prompt=body.prompt,
                correlation_id=correlation_id,
                on_event=on_event,
                user_id=body.user_id,
            )
        )

        try:
            while not pipeline_task.done():
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                    if event is not None:
                        yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"

            # Drain remaining events
            while not event_queue.empty():
                event = event_queue.get_nowait()
                if event is not None:
                    yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"

            digest = pipeline_task.result()
            yield f"event: complete\ndata: {json.dumps(digest.model_dump(mode='json'))}\n\n"

        except Exception as exc:
            logger.error("Streaming pipeline error: %s", exc)
            error_data = {"code": "PIPELINE_ERROR", "message": str(exc)}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            settings.correlation_id_header: correlation_id,
        },
    )
