"""FastAPI route definitions for the Traceability Store.

Endpoints are split into three groups:
  - Write endpoints (called by Agent Orchestrator): POST /api/reports, ...
  - Read endpoints (called by Web App / dashboards): GET /api/reports, ...
  - Metrics endpoints: GET /api/metrics/...
  - Health check: GET /health
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    CreateReportRequest,
    CreateSourcesRequest,
    CreateToolCallRequest,
    ErrorRateResponse,
    ErrorResponse,
    PaginatedReportsResponse,
    ReportDetailResponse,
    ReportSummaryResponse,
    SourceResponse,
    ToolCallResponse,
    ToolErrorStat,
    ToolLatencyResponse,
    UserProfileResponse,
    UserProfileUpsert,
)
from src.db.engine import get_session
from src.db.repositories import (
    ReportRepository,
    SourceRepository,
    ToolCallRepository,
    UserProfileRepository,
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

reports_router = APIRouter(prefix="/api/reports", tags=["reports"])
metrics_router = APIRouter(prefix="/api/metrics", tags=["metrics"])
profiles_router = APIRouter(prefix="/api/profiles", tags=["profiles"])

# Session dependency alias
SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Standard 404 / 409 error responses for OpenAPI docs
_NOT_FOUND_RESPONSES: dict = {
    404: {"model": ErrorResponse, "description": "Report not found"},
}
_CONFLICT_RESPONSES: dict = {
    409: {"model": ErrorResponse, "description": "Report already exists"},
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _report_not_found(report_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": {
                "code": "REPORT_NOT_FOUND",
                "message": f"Report '{report_id}' does not exist.",
                "details": {"report_id": report_id},
                "retry_after_seconds": None,
            }
        },
    )


# ---------------------------------------------------------------------------
# Write endpoints
# ---------------------------------------------------------------------------


@reports_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ReportDetailResponse,
    responses=_CONFLICT_RESPONSES,
    summary="Create a new digest report",
    description=(
        "Called by the Agent Orchestrator after generating a digest. "
        "Persists the full structured digest and its metadata."
    ),
)
async def create_report(
    payload: CreateReportRequest,
    session: SessionDep,
) -> ReportDetailResponse:
    """Persist a new digest report.

    Returns the created report (201). Returns 409 if ``report_id`` already exists.
    """
    repo = ReportRepository(session)
    try:
        report = await repo.create(
            report_id=payload.report_id,
            digest_type=payload.digest_type,
            query=payload.query,
            digest_json=payload.digest_json,
            generated_at=payload.generated_at,
            user_id=payload.user_id,
        )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "REPORT_ALREADY_EXISTS",
                    "message": f"Report '{payload.report_id}' already exists.",
                    "details": {"report_id": payload.report_id},
                    "retry_after_seconds": None,
                }
            },
        )
    return ReportDetailResponse.model_validate(report)


@reports_router.post(
    "/{report_id}/tool-calls",
    status_code=status.HTTP_201_CREATED,
    response_model=ToolCallResponse,
    responses=_NOT_FOUND_RESPONSES,
    summary="Log a tool call for a report",
    description="Records a single MCP tool call against an existing report.",
)
async def create_tool_call(
    report_id: str,
    payload: CreateToolCallRequest,
    session: SessionDep,
) -> ToolCallResponse:
    """Log an MCP tool call. Returns 404 if the parent report is not found."""
    report_repo = ReportRepository(session)
    report = await report_repo.get_by_report_id(report_id)
    if not report:
        raise _report_not_found(report_id)

    tool_repo = ToolCallRepository(session)
    tool_call = await tool_repo.create(
        report_id=report_id,
        tool_name=payload.tool_name,
        input_json=payload.input_json,
        output_json=payload.output_json,
        latency_ms=payload.latency_ms,
        status=payload.status,
        error_message=payload.error_message,
        timestamp=payload.timestamp,
    )
    await session.commit()
    return ToolCallResponse.model_validate(tool_call)


@reports_router.post(
    "/{report_id}/sources",
    status_code=status.HTTP_201_CREATED,
    response_model=list[SourceResponse],
    responses=_NOT_FOUND_RESPONSES,
    summary="Bulk-add sources for a report",
    description="Records all source articles referenced in a digest. Accepts a list.",
)
async def create_sources(
    report_id: str,
    payload: CreateSourcesRequest,
    session: SessionDep,
) -> list[SourceResponse]:
    """Bulk-insert source articles. Returns 404 if the parent report is not found."""
    report_repo = ReportRepository(session)
    report = await report_repo.get_by_report_id(report_id)
    if not report:
        raise _report_not_found(report_id)

    source_repo = SourceRepository(session)
    sources = await source_repo.create_many(
        report_id=report_id,
        sources_data=[s.model_dump() for s in payload.sources],
    )
    await session.commit()
    return [SourceResponse.model_validate(src) for src in sources]


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------


@reports_router.get(
    "",
    response_model=PaginatedReportsResponse,
    summary="List reports (paginated)",
    description=(
        "Returns a paginated list of report summaries. "
        "Filter by digest_type, user_id, or date range."
    ),
)
async def list_reports(
    session: SessionDep,
    digest_type: str | None = Query(default=None, description="Filter by digest type"),
    user_id: str | None = Query(default=None, description="Filter by user ID"),
    from_dt: datetime | None = Query(
        default=None, alias="from", description="Start of generated_at range (ISO 8601 UTC)"
    ),
    to_dt: datetime | None = Query(
        default=None, alias="to", description="End of generated_at range (ISO 8601 UTC)"
    ),
    limit: int = Query(default=50, ge=1, le=500, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
) -> PaginatedReportsResponse:
    """Return a paginated list of report summaries."""
    repo = ReportRepository(session)
    reports = await repo.list_reports(
        digest_type=digest_type,
        user_id=user_id,
        from_dt=from_dt,
        to_dt=to_dt,
        limit=limit,
        offset=offset,
    )
    total = await repo.count_reports(
        digest_type=digest_type,
        user_id=user_id,
        from_dt=from_dt,
        to_dt=to_dt,
    )
    return PaginatedReportsResponse(
        items=[ReportSummaryResponse.model_validate(r) for r in reports],
        total=total,
        limit=limit,
        offset=offset,
    )


@reports_router.get(
    "/{report_id}",
    response_model=ReportDetailResponse,
    responses=_NOT_FOUND_RESPONSES,
    summary="Get a single report",
    description="Returns the full report including the complete digest_json.",
)
async def get_report(report_id: str, session: SessionDep) -> ReportDetailResponse:
    """Fetch a report by its human-readable ID. Returns 404 if not found."""
    repo = ReportRepository(session)
    report = await repo.get_by_report_id(report_id)
    if not report:
        raise _report_not_found(report_id)
    return ReportDetailResponse.model_validate(report)


@reports_router.get(
    "/{report_id}/tool-calls",
    response_model=list[ToolCallResponse],
    responses=_NOT_FOUND_RESPONSES,
    summary="List tool calls for a report",
    description="Returns all tool calls for a report, ordered by timestamp ascending.",
)
async def list_tool_calls(report_id: str, session: SessionDep) -> list[ToolCallResponse]:
    """Return all tool calls for a report. Returns 404 if the report is not found."""
    report_repo = ReportRepository(session)
    report = await report_repo.get_by_report_id(report_id)
    if not report:
        raise _report_not_found(report_id)

    tool_repo = ToolCallRepository(session)
    calls = await tool_repo.list_for_report(report_id)
    return [ToolCallResponse.model_validate(c) for c in calls]


@reports_router.get(
    "/{report_id}/sources",
    response_model=list[SourceResponse],
    responses=_NOT_FOUND_RESPONSES,
    summary="List sources for a report",
    description="Returns all source articles recorded for a report.",
)
async def list_sources(report_id: str, session: SessionDep) -> list[SourceResponse]:
    """Return all sources for a report. Returns 404 if the report is not found."""
    report_repo = ReportRepository(session)
    report = await report_repo.get_by_report_id(report_id)
    if not report:
        raise _report_not_found(report_id)

    source_repo = SourceRepository(session)
    sources = await source_repo.list_for_report(report_id)
    return [SourceResponse.model_validate(src) for src in sources]


# ---------------------------------------------------------------------------
# Metrics endpoints
# ---------------------------------------------------------------------------


@metrics_router.get(
    "/tool-latency",
    response_model=ToolLatencyResponse,
    summary="Tool latency percentiles",
    description=(
        "Returns p50/p95/p99 latency statistics for successful tool calls. "
        "Optionally filter by tool_name and date range."
    ),
)
async def tool_latency(
    session: SessionDep,
    tool_name: str | None = Query(default=None, description="Filter to a specific tool"),
    from_dt: datetime | None = Query(
        default=None, alias="from", description="Start of timestamp range"
    ),
    to_dt: datetime | None = Query(
        default=None, alias="to", description="End of timestamp range"
    ),
) -> ToolLatencyResponse:
    """Return latency percentile statistics for MCP tool calls."""
    repo = ToolCallRepository(session)
    stats = await repo.get_latency_stats(tool_name=tool_name, from_dt=from_dt, to_dt=to_dt)
    return ToolLatencyResponse(**stats)


@metrics_router.get(
    "/error-rate",
    response_model=ErrorRateResponse,
    summary="Tool error rate",
    description=(
        "Returns aggregate and per-tool error rates. "
        "Optionally filter by tool_name and date range."
    ),
)
async def error_rate(
    session: SessionDep,
    tool_name: str | None = Query(default=None, description="Filter to a specific tool"),
    from_dt: datetime | None = Query(
        default=None, alias="from", description="Start of timestamp range"
    ),
    to_dt: datetime | None = Query(
        default=None, alias="to", description="End of timestamp range"
    ),
) -> ErrorRateResponse:
    """Return error-rate metrics for MCP tool calls."""
    repo = ToolCallRepository(session)
    stats = await repo.get_error_rate(tool_name=tool_name, from_dt=from_dt, to_dt=to_dt)
    return ErrorRateResponse(
        total=stats["total"],
        errors=stats["errors"],
        error_rate=stats["error_rate"],
        by_tool=[ToolErrorStat(**t) for t in stats["by_tool"]],
    )


# ---------------------------------------------------------------------------
# User profile endpoints
# ---------------------------------------------------------------------------


@profiles_router.get(
    "/{user_id}",
    response_model=UserProfileResponse,
    responses=_NOT_FOUND_RESPONSES,
    summary="Get a user profile",
    description="Returns the user profile for the given user_id, or 404 if none exists.",
)
async def get_user_profile(user_id: str, session: SessionDep) -> UserProfileResponse:
    repo = UserProfileRepository(session)
    profile = await repo.get_by_user_id(user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "PROFILE_NOT_FOUND",
                    "message": f"No profile found for user '{user_id}'.",
                    "details": {"user_id": user_id},
                    "retry_after_seconds": None,
                }
            },
        )
    return UserProfileResponse.model_validate(profile)


@profiles_router.put(
    "/{user_id}",
    response_model=UserProfileResponse,
    summary="Create or update a user profile",
    description="Upserts the user profile. Creates if it doesn't exist, updates if it does.",
)
async def upsert_user_profile(
    user_id: str,
    payload: UserProfileUpsert,
    session: SessionDep,
) -> UserProfileResponse:
    repo = UserProfileRepository(session)
    profile = await repo.upsert(
        user_id=user_id,
        display_name=payload.display_name,
        context=payload.context,
    )
    await session.commit()
    return UserProfileResponse.model_validate(profile)
