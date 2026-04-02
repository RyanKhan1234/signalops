"""FastAPI application factory for the Agent Orchestrator."""

from __future__ import annotations

import logging
import uuid

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes import router
from src.config import settings

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="SignalOps Agent Orchestrator",
        description=(
            "LangChain/LangGraph-based personal research agent pipeline. "
            "Takes natural language prompts and returns structured, source-attributed research digests."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ---------------------------------------------------------------------------
    # Middleware
    # ---------------------------------------------------------------------------

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Tighten in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next: object) -> Response:
        """Inject and propagate X-Request-ID through every request."""
        # call_next is typed as Any in the middleware protocol
        correlation_id = request.headers.get(settings.correlation_id_header, str(uuid.uuid4()))
        request.state.correlation_id = correlation_id

        response: Response = await call_next(request)  # type: ignore[operator]
        response.headers[settings.correlation_id_header] = correlation_id
        return response

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next: object) -> Response:
        """Log all incoming requests and responses."""
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            correlation_id=getattr(request.state, "correlation_id", ""),
        )
        response: Response = await call_next(request)  # type: ignore[operator]
        logger.info(
            "response",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )
        return response

    # ---------------------------------------------------------------------------
    # Exception handlers
    # ---------------------------------------------------------------------------

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all exception handler that returns structured error JSON."""
        logger.error("Unhandled exception", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                    "details": {},
                    "retry_after_seconds": None,
                }
            },
        )

    # ---------------------------------------------------------------------------
    # Startup / shutdown events
    # ---------------------------------------------------------------------------

    @app.on_event("startup")
    async def on_startup() -> None:
        logging.basicConfig(level=settings.log_level.upper())
        logger.info(
            "SignalOps Agent Orchestrator starting",
            version="0.1.0",
            mcp_wrapper_url=settings.mcp_wrapper_url,
            traceability_store_url=settings.traceability_store_url,
            model=settings.anthropic_model,
        )

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        logger.info("SignalOps Agent Orchestrator shutting down")

    # ---------------------------------------------------------------------------
    # Include routes
    # ---------------------------------------------------------------------------

    app.include_router(router)

    return app
