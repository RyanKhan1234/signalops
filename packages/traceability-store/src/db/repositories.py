"""Repository layer — all database access goes through these classes.

Routes must never import SQLAlchemy models directly. Instead they use these
repositories to read and write data. This keeps SQL out of the API layer and
makes the persistence logic independently testable.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Report, Source, ToolCall, UserProfile


# ---------------------------------------------------------------------------
# Report repository
# ---------------------------------------------------------------------------


class ReportRepository:
    """CRUD operations for the reports table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        report_id: str,
        digest_type: str,
        query: str,
        digest_json: dict,
        generated_at: datetime,
        user_id: str | None = None,
    ) -> Report:
        """Persist a new report row and return the saved instance.

        Args:
            report_id: Human-readable identifier (e.g., ``rpt_abc123``).
            digest_type: One of ``daily_digest``, ``weekly_report``,
                ``risk_alert``, ``competitor_monitor``.
            query: The original natural-language prompt from the user.
            digest_json: Full structured digest as a Python dict (stored as JSONB).
            generated_at: UTC timestamp of when the digest was generated.
            user_id: Optional user identifier for multi-user filtering.

        Returns:
            The newly created :class:`Report` ORM instance.
        """
        report = Report(
            report_id=report_id,
            digest_type=digest_type,
            query=query,
            digest_json=digest_json,
            generated_at=generated_at,
            user_id=user_id,
        )
        self._session.add(report)
        await self._session.flush()
        await self._session.refresh(report)
        return report

    async def get_by_report_id(self, report_id: str) -> Report | None:
        """Fetch a single report by its human-readable ``report_id``.

        Args:
            report_id: The human-readable report identifier.

        Returns:
            The :class:`Report` instance or ``None`` if not found.
        """
        result = await self._session.execute(
            select(Report).where(Report.report_id == report_id)
        )
        return result.scalar_one_or_none()

    async def list_reports(
        self,
        *,
        digest_type: str | None = None,
        user_id: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Report]:
        """Return a paginated, optionally-filtered list of reports.

        Args:
            digest_type: Filter by digest type.
            user_id: Filter by user identifier.
            from_dt: Inclusive start of ``generated_at`` range.
            to_dt: Inclusive end of ``generated_at`` range.
            limit: Maximum number of rows to return (default 50).
            offset: Number of rows to skip (default 0).

        Returns:
            List of :class:`Report` instances ordered by ``generated_at`` descending.
        """
        stmt = select(Report)
        if digest_type:
            stmt = stmt.where(Report.digest_type == digest_type)
        if user_id:
            stmt = stmt.where(Report.user_id == user_id)
        if from_dt:
            stmt = stmt.where(Report.generated_at >= from_dt)
        if to_dt:
            stmt = stmt.where(Report.generated_at <= to_dt)
        stmt = stmt.order_by(Report.generated_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_reports(
        self,
        *,
        digest_type: str | None = None,
        user_id: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> int:
        """Count reports matching the given filters (used for pagination metadata).

        Args:
            digest_type: Filter by digest type.
            user_id: Filter by user identifier.
            from_dt: Inclusive start of ``generated_at`` range.
            to_dt: Inclusive end of ``generated_at`` range.

        Returns:
            Integer count of matching rows.
        """
        stmt = select(func.count()).select_from(Report)
        if digest_type:
            stmt = stmt.where(Report.digest_type == digest_type)
        if user_id:
            stmt = stmt.where(Report.user_id == user_id)
        if from_dt:
            stmt = stmt.where(Report.generated_at >= from_dt)
        if to_dt:
            stmt = stmt.where(Report.generated_at <= to_dt)
        result = await self._session.execute(stmt)
        return result.scalar_one()


# ---------------------------------------------------------------------------
# Tool call repository
# ---------------------------------------------------------------------------


class ToolCallRepository:
    """CRUD operations for the tool_calls table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        report_id: str,
        tool_name: str,
        input_json: dict,
        latency_ms: int,
        status: str,
        timestamp: datetime,
        output_json: dict | None = None,
        error_message: str | None = None,
    ) -> ToolCall:
        """Persist a new tool call row.

        Args:
            report_id: Parent report identifier.
            tool_name: Name of the MCP tool (e.g., ``search_news``).
            input_json: Tool call input parameters as a dict.
            latency_ms: Execution time in milliseconds.
            status: One of ``success``, ``error``, ``timeout``.
            timestamp: UTC timestamp of when the tool was called.
            output_json: Tool call output (``None`` on failure).
            error_message: Error details when ``status != success``.

        Returns:
            The newly created :class:`ToolCall` ORM instance.
        """
        tool_call = ToolCall(
            report_id=report_id,
            tool_name=tool_name,
            input_json=input_json,
            output_json=output_json,
            latency_ms=latency_ms,
            status=status,
            error_message=error_message,
            timestamp=timestamp,
        )
        self._session.add(tool_call)
        await self._session.flush()
        await self._session.refresh(tool_call)
        return tool_call

    async def list_for_report(self, report_id: str) -> list[ToolCall]:
        """Return all tool calls for a report, ordered by timestamp ascending.

        Args:
            report_id: Parent report identifier.

        Returns:
            List of :class:`ToolCall` instances.
        """
        result = await self._session.execute(
            select(ToolCall)
            .where(ToolCall.report_id == report_id)
            .order_by(ToolCall.timestamp.asc())
        )
        return list(result.scalars().all())

    async def get_latency_stats(
        self,
        *,
        tool_name: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> dict[str, Any]:
        """Compute latency percentiles using Python-side aggregation.

        Fetches latency values for successful calls and computes p50/p95/p99
        in Python so the same code works with both PostgreSQL and SQLite (tests).

        Args:
            tool_name: Filter to a specific tool (``None`` = all tools).
            from_dt: Inclusive start of ``timestamp`` range.
            to_dt: Inclusive end of ``timestamp`` range.

        Returns:
            Dict with keys ``p50_ms``, ``p95_ms``, ``p99_ms``, ``avg_ms``, ``count``.
        """
        stmt = select(ToolCall.latency_ms).where(ToolCall.status == "success")
        if tool_name:
            stmt = stmt.where(ToolCall.tool_name == tool_name)
        if from_dt:
            stmt = stmt.where(ToolCall.timestamp >= from_dt)
        if to_dt:
            stmt = stmt.where(ToolCall.timestamp <= to_dt)

        result = await self._session.execute(stmt)
        latencies = sorted(row[0] for row in result.all())

        if not latencies:
            return {"p50_ms": None, "p95_ms": None, "p99_ms": None, "avg_ms": None, "count": 0}

        def percentile(data: list[int], pct: float) -> int:
            idx = max(0, int(len(data) * pct / 100) - 1)
            return data[min(idx, len(data) - 1)]

        return {
            "p50_ms": percentile(latencies, 50),
            "p95_ms": percentile(latencies, 95),
            "p99_ms": percentile(latencies, 99),
            "avg_ms": round(sum(latencies) / len(latencies)),
            "count": len(latencies),
        }

    async def get_error_rate(
        self,
        *,
        tool_name: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> dict[str, Any]:
        """Compute error-rate metrics, optionally broken down per tool.

        Aggregates in Python to remain cross-dialect (PostgreSQL + SQLite tests).

        Args:
            tool_name: Filter to a specific tool (``None`` = all tools).
            from_dt: Inclusive start of ``timestamp`` range.
            to_dt: Inclusive end of ``timestamp`` range.

        Returns:
            Dict with keys ``total``, ``errors``, ``error_rate``, ``by_tool``.
        """
        stmt = select(ToolCall.tool_name, ToolCall.status)
        if tool_name:
            stmt = stmt.where(ToolCall.tool_name == tool_name)
        if from_dt:
            stmt = stmt.where(ToolCall.timestamp >= from_dt)
        if to_dt:
            stmt = stmt.where(ToolCall.timestamp <= to_dt)

        result = await self._session.execute(stmt)
        rows = result.all()

        # Aggregate per tool in Python
        tool_stats: dict[str, dict[str, int]] = {}
        for row in rows:
            name = row.tool_name
            if name not in tool_stats:
                tool_stats[name] = {"total": 0, "errors": 0}
            tool_stats[name]["total"] += 1
            if row.status != "success":
                tool_stats[name]["errors"] += 1

        by_tool = []
        grand_total = 0
        grand_errors = 0
        for name, stats in tool_stats.items():
            t = stats["total"]
            e = stats["errors"]
            grand_total += t
            grand_errors += e
            by_tool.append(
                {
                    "tool_name": name,
                    "total": t,
                    "errors": e,
                    "error_rate": round(e / t, 4) if t else 0.0,
                }
            )

        return {
            "total": grand_total,
            "errors": grand_errors,
            "error_rate": round(grand_errors / grand_total, 4) if grand_total else 0.0,
            "by_tool": by_tool,
        }


# ---------------------------------------------------------------------------
# Source repository
# ---------------------------------------------------------------------------


class SourceRepository:
    """CRUD operations for the sources table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(
        self,
        report_id: str,
        sources_data: list[dict],
    ) -> list[Source]:
        """Bulk-insert source rows for a report.

        Args:
            report_id: Parent report identifier.
            sources_data: List of dicts with keys matching :class:`Source` columns
                (``url``, ``title``, ``source_name``, ``published_date``,
                ``snippet``, ``accessed_at``).

        Returns:
            List of newly created :class:`Source` ORM instances.
        """
        sources = [
            Source(
                report_id=report_id,
                url=s["url"],
                title=s["title"],
                source_name=s.get("source_name"),
                published_date=s.get("published_date"),
                snippet=s.get("snippet"),
                accessed_at=s["accessed_at"],
            )
            for s in sources_data
        ]
        self._session.add_all(sources)
        await self._session.flush()
        for src in sources:
            await self._session.refresh(src)
        return sources

    async def list_for_report(self, report_id: str) -> list[Source]:
        """Return all sources for a report, ordered by accessed_at ascending.

        Args:
            report_id: Parent report identifier.

        Returns:
            List of :class:`Source` instances.
        """
        result = await self._session.execute(
            select(Source)
            .where(Source.report_id == report_id)
            .order_by(Source.accessed_at.asc())
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# User profile repository
# ---------------------------------------------------------------------------


class UserProfileRepository:
    """CRUD operations for the user_profiles table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: str) -> UserProfile | None:
        result = await self._session.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        user_id: str,
        display_name: str | None = None,
        context: str = "",
    ) -> UserProfile:
        """Create or update a user profile.

        If a row with the given ``user_id`` already exists its ``display_name``,
        ``context``, and ``updated_at`` fields are overwritten.  Otherwise a new
        row is inserted.
        """
        existing = await self.get_by_user_id(user_id)
        if existing is not None:
            existing.display_name = display_name
            existing.context = context
            # Manually bump updated_at for SQLite compat (no onupdate trigger)
            from datetime import datetime, timezone
            existing.updated_at = datetime.now(tz=timezone.utc)
            await self._session.flush()
            await self._session.refresh(existing)
            return existing

        profile = UserProfile(
            user_id=user_id,
            display_name=display_name,
            context=context,
        )
        self._session.add(profile)
        await self._session.flush()
        await self._session.refresh(profile)
        return profile
