"""Unit tests for the repository layer.

Tests run against an in-memory SQLite database via aiosqlite. Each test
gets a fresh database (function-scoped fixtures).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.db.repositories import ReportRepository, SourceRepository, ToolCallRepository
from tests.conftest import make_report_payload, make_source_payload, make_tool_call_payload

UTC = timezone.utc


# ---------------------------------------------------------------------------
# ReportRepository tests
# ---------------------------------------------------------------------------


class TestReportRepository:
    async def test_create_and_retrieve_report(self, session):
        """A created report should be retrievable by report_id."""
        repo = ReportRepository(session)
        report = await repo.create(
            report_id="rpt_001",
            digest_type="weekly_report",
            query="Test query",
            digest_json={"executive_summary": "Summary"},
            generated_at=datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC),
            user_id="user_1",
        )
        await session.commit()

        fetched = await repo.get_by_report_id("rpt_001")
        assert fetched is not None
        assert fetched.report_id == "rpt_001"
        assert fetched.digest_type == "weekly_report"
        assert fetched.user_id == "user_1"
        assert fetched.digest_json == {"executive_summary": "Summary"}

    async def test_get_nonexistent_report_returns_none(self, session):
        """Fetching a report that does not exist should return None."""
        repo = ReportRepository(session)
        result = await repo.get_by_report_id("rpt_missing")
        assert result is None

    async def test_list_reports_returns_all(self, session):
        """list_reports should return all reports when no filters are applied."""
        repo = ReportRepository(session)
        for i in range(3):
            await repo.create(
                report_id=f"rpt_{i:03d}",
                digest_type="daily_digest",
                query=f"Query {i}",
                digest_json={},
                generated_at=datetime(2026, 3, 1, i, 0, 0, tzinfo=UTC),
            )
        await session.commit()

        reports = await repo.list_reports()
        assert len(reports) == 3

    async def test_list_reports_filtered_by_digest_type(self, session):
        """list_reports should filter by digest_type correctly."""
        repo = ReportRepository(session)
        await repo.create(
            report_id="rpt_daily",
            digest_type="daily_digest",
            query="daily q",
            digest_json={},
            generated_at=datetime(2026, 3, 1, 8, 0, tzinfo=UTC),
        )
        await repo.create(
            report_id="rpt_weekly",
            digest_type="weekly_report",
            query="weekly q",
            digest_json={},
            generated_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
        )
        await session.commit()

        dailies = await repo.list_reports(digest_type="daily_digest")
        assert len(dailies) == 1
        assert dailies[0].report_id == "rpt_daily"

    async def test_list_reports_paginated(self, session):
        """limit and offset should paginate results correctly."""
        repo = ReportRepository(session)
        for i in range(5):
            await repo.create(
                report_id=f"rpt_{i:03d}",
                digest_type="daily_digest",
                query=f"Q{i}",
                digest_json={},
                generated_at=datetime(2026, 3, 1, i, 0, tzinfo=UTC),
            )
        await session.commit()

        page1 = await repo.list_reports(limit=2, offset=0)
        page2 = await repo.list_reports(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        # IDs should not overlap
        ids1 = {r.report_id for r in page1}
        ids2 = {r.report_id for r in page2}
        assert ids1.isdisjoint(ids2)

    async def test_count_reports(self, session):
        """count_reports should return the total matching count."""
        repo = ReportRepository(session)
        for i in range(4):
            await repo.create(
                report_id=f"rpt_c{i}",
                digest_type="risk_alert",
                query=f"Q{i}",
                digest_json={},
                generated_at=datetime(2026, 3, 1, tzinfo=UTC),
            )
        await session.commit()

        total = await repo.count_reports(digest_type="risk_alert")
        assert total == 4

    async def test_list_reports_filtered_by_date_range(self, session):
        """from_dt and to_dt should filter reports by generated_at."""
        repo = ReportRepository(session)
        await repo.create(
            report_id="rpt_old",
            digest_type="daily_digest",
            query="old",
            digest_json={},
            generated_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
        await repo.create(
            report_id="rpt_new",
            digest_type="daily_digest",
            query="new",
            digest_json={},
            generated_at=datetime(2026, 3, 1, tzinfo=UTC),
        )
        await session.commit()

        results = await repo.list_reports(
            from_dt=datetime(2026, 2, 15, tzinfo=UTC),
            to_dt=datetime(2026, 3, 15, tzinfo=UTC),
        )
        assert len(results) == 1
        assert results[0].report_id == "rpt_new"


# ---------------------------------------------------------------------------
# ToolCallRepository tests
# ---------------------------------------------------------------------------


class TestToolCallRepository:
    async def _create_report(self, session) -> str:
        """Helper: create a parent report and return its report_id."""
        repo = ReportRepository(session)
        await repo.create(
            report_id="rpt_parent",
            digest_type="weekly_report",
            query="q",
            digest_json={},
            generated_at=datetime(2026, 3, 1, tzinfo=UTC),
        )
        await session.commit()
        return "rpt_parent"

    async def test_create_and_list_tool_calls(self, session):
        """Tool calls should be persisted and listable by report_id."""
        report_id = await self._create_report(session)
        repo = ToolCallRepository(session)

        await repo.create(
            report_id=report_id,
            tool_name="search_news",
            input_json={"query": "test"},
            latency_ms=300,
            status="success",
            timestamp=datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
        )
        await session.commit()

        calls = await repo.list_for_report(report_id)
        assert len(calls) == 1
        assert calls[0].tool_name == "search_news"
        assert calls[0].latency_ms == 300
        assert calls[0].status == "success"

    async def test_tool_calls_ordered_by_timestamp(self, session):
        """list_for_report should order calls by timestamp ascending."""
        report_id = await self._create_report(session)
        repo = ToolCallRepository(session)

        for i, ts_hour in enumerate([3, 1, 2]):
            await repo.create(
                report_id=report_id,
                tool_name=f"tool_{i}",
                input_json={},
                latency_ms=100 * (i + 1),
                status="success",
                timestamp=datetime(2026, 3, 1, ts_hour, 0, tzinfo=UTC),
            )
        await session.commit()

        calls = await repo.list_for_report(report_id)
        timestamps = [c.timestamp for c in calls]
        assert timestamps == sorted(timestamps)

    async def test_latency_stats_with_data(self, session):
        """get_latency_stats should compute percentiles from successful calls."""
        report_id = await self._create_report(session)
        repo = ToolCallRepository(session)

        latencies = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        for i, ms in enumerate(latencies):
            await repo.create(
                report_id=report_id,
                tool_name="search_news",
                input_json={},
                latency_ms=ms,
                status="success",
                timestamp=datetime(2026, 3, 1, 0, i, tzinfo=UTC),
            )
        await session.commit()

        stats = await repo.get_latency_stats()
        assert stats["count"] == 10
        assert stats["p50_ms"] is not None
        assert stats["p95_ms"] is not None
        assert stats["p99_ms"] is not None
        assert stats["avg_ms"] == 550  # mean of 100..1000

    async def test_latency_stats_no_data_returns_nulls(self, session):
        """get_latency_stats with no data should return None percentiles and count 0."""
        repo = ToolCallRepository(session)
        stats = await repo.get_latency_stats()
        assert stats["count"] == 0
        assert stats["p50_ms"] is None

    async def test_error_rate_mixed_statuses(self, session):
        """get_error_rate should correctly compute error fraction per tool."""
        report_id = await self._create_report(session)
        repo = ToolCallRepository(session)

        # 3 success + 1 error for search_news → error_rate = 0.25
        for i in range(3):
            await repo.create(
                report_id=report_id,
                tool_name="search_news",
                input_json={},
                latency_ms=200,
                status="success",
                timestamp=datetime(2026, 3, 1, 0, i, tzinfo=UTC),
            )
        await repo.create(
            report_id=report_id,
            tool_name="search_news",
            input_json={},
            latency_ms=30000,
            status="timeout",
            error_message="Timeout",
            timestamp=datetime(2026, 3, 1, 0, 10, tzinfo=UTC),
        )
        await session.commit()

        stats = await repo.get_error_rate(tool_name="search_news")
        assert stats["total"] == 4
        assert stats["errors"] == 1
        assert stats["error_rate"] == pytest.approx(0.25, abs=0.001)

    async def test_error_rate_no_data(self, session):
        """get_error_rate with no matching rows should return zeros."""
        repo = ToolCallRepository(session)
        stats = await repo.get_error_rate()
        assert stats["total"] == 0
        assert stats["errors"] == 0
        assert stats["error_rate"] == 0.0


# ---------------------------------------------------------------------------
# SourceRepository tests
# ---------------------------------------------------------------------------


class TestSourceRepository:
    async def _create_report(self, session, report_id: str = "rpt_src") -> str:
        repo = ReportRepository(session)
        await repo.create(
            report_id=report_id,
            digest_type="daily_digest",
            query="q",
            digest_json={},
            generated_at=datetime(2026, 3, 1, tzinfo=UTC),
        )
        await session.commit()
        return report_id

    async def test_create_many_and_list(self, session):
        """create_many should persist all sources; list_for_report should return them."""
        report_id = await self._create_report(session)
        repo = SourceRepository(session)

        sources_data = [
            {
                "url": "https://example.com/article-1",
                "title": "Article One",
                "source_name": "TechCrunch",
                "published_date": datetime(2026, 2, 28, tzinfo=UTC),
                "snippet": "Snippet one",
                "accessed_at": datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
            },
            {
                "url": "https://example.com/article-2",
                "title": "Article Two",
                "source_name": None,
                "published_date": None,
                "snippet": None,
                "accessed_at": datetime(2026, 3, 1, 12, 1, tzinfo=UTC),
            },
        ]
        created = await repo.create_many(report_id, sources_data)
        await session.commit()
        assert len(created) == 2

        listed = await repo.list_for_report(report_id)
        assert len(listed) == 2
        urls = {s.url for s in listed}
        assert "https://example.com/article-1" in urls
        assert "https://example.com/article-2" in urls

    async def test_sources_ordered_by_accessed_at(self, session):
        """list_for_report should order sources by accessed_at ascending."""
        report_id = await self._create_report(session)
        repo = SourceRepository(session)

        sources_data = [
            {
                "url": f"https://example.com/{i}",
                "title": f"Article {i}",
                "accessed_at": datetime(2026, 3, 1, i, 0, tzinfo=UTC),
            }
            for i in [3, 1, 2]
        ]
        await repo.create_many(report_id, sources_data)
        await session.commit()

        listed = await repo.list_for_report(report_id)
        times = [s.accessed_at for s in listed]
        assert times == sorted(times)
