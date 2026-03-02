"""Integration tests for the FastAPI HTTP endpoints.

Uses an httpx AsyncClient wired to an in-memory SQLite database. No
PostgreSQL required.
"""

from __future__ import annotations

import pytest

from tests.conftest import make_report_payload, make_source_payload, make_tool_call_payload


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealth:
    async def test_health_returns_200(self, client):
        """GET /health should return 200 when the service is up."""
        resp = await client.get("/health")
        assert resp.status_code == 200

    async def test_health_body_shape(self, client):
        """Health response should contain status and db_connected fields."""
        resp = await client.get("/health")
        body = resp.json()
        assert "status" in body
        assert "db_connected" in body
        # DB is always connected in test because we use an in-memory SQLite
        assert body["db_connected"] is True
        assert body["status"] == "healthy"


# ---------------------------------------------------------------------------
# POST /api/reports
# ---------------------------------------------------------------------------


class TestCreateReport:
    async def test_create_report_returns_201(self, client):
        """Creating a valid report should return 201 Created."""
        resp = await client.post("/api/reports", json=make_report_payload())
        assert resp.status_code == 201

    async def test_create_report_response_shape(self, client):
        """Response should include all report fields."""
        payload = make_report_payload(report_id="rpt_shape_test")
        resp = await client.post("/api/reports", json=payload)
        body = resp.json()
        assert body["report_id"] == "rpt_shape_test"
        assert body["digest_type"] == "weekly_report"
        assert "id" in body
        assert "created_at" in body
        assert "digest_json" in body

    async def test_create_duplicate_report_returns_409(self, client):
        """Submitting the same report_id twice should return 409."""
        payload = make_report_payload(report_id="rpt_dup")
        await client.post("/api/reports", json=payload)
        resp = await client.post("/api/reports", json=payload)
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"]["code"] == "REPORT_ALREADY_EXISTS"

    async def test_create_report_without_user_id(self, client):
        """user_id is optional — omitting it should still return 201."""
        payload = make_report_payload(report_id="rpt_no_user")
        del payload["user_id"]
        resp = await client.post("/api/reports", json=payload)
        assert resp.status_code == 201
        assert resp.json()["user_id"] is None

    async def test_create_report_invalid_digest_type_returns_422(self, client):
        """An unrecognised digest_type should fail Pydantic validation (422)."""
        payload = make_report_payload()
        payload["digest_type"] = "invalid_type"
        resp = await client.post("/api/reports", json=payload)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/reports
# ---------------------------------------------------------------------------


class TestListReports:
    async def _seed(self, client, n: int = 3) -> list[str]:
        ids = []
        for i in range(n):
            p = make_report_payload(
                report_id=f"rpt_list_{i:03d}",
                digest_type="daily_digest" if i % 2 == 0 else "weekly_report",
            )
            p["generated_at"] = f"2026-03-0{i + 1}T12:00:00Z"
            await client.post("/api/reports", json=p)
            ids.append(f"rpt_list_{i:03d}")
        return ids

    async def test_list_returns_all_reports(self, client):
        await self._seed(client, 3)
        resp = await client.get("/api/reports")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3

    async def test_list_pagination(self, client):
        await self._seed(client, 5)
        resp = await client.get("/api/reports?limit=2&offset=0")
        body = resp.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["limit"] == 2
        assert body["offset"] == 0

    async def test_list_filter_by_digest_type(self, client):
        await self._seed(client, 4)
        resp = await client.get("/api/reports?digest_type=daily_digest")
        body = resp.json()
        assert all(r["digest_type"] == "daily_digest" for r in body["items"])

    async def test_list_no_digest_json_in_summary(self, client):
        """List endpoint should NOT include digest_json to keep responses slim."""
        await self._seed(client, 1)
        resp = await client.get("/api/reports")
        item = resp.json()["items"][0]
        assert "digest_json" not in item


# ---------------------------------------------------------------------------
# GET /api/reports/{report_id}
# ---------------------------------------------------------------------------


class TestGetReport:
    async def test_get_report_returns_full_digest(self, client):
        """GET single report should include digest_json."""
        await client.post("/api/reports", json=make_report_payload("rpt_full"))
        resp = await client.get("/api/reports/rpt_full")
        assert resp.status_code == 200
        body = resp.json()
        assert body["report_id"] == "rpt_full"
        assert "digest_json" in body

    async def test_get_nonexistent_report_returns_404(self, client):
        resp = await client.get("/api/reports/rpt_missing")
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "REPORT_NOT_FOUND"


# ---------------------------------------------------------------------------
# POST /api/reports/{report_id}/tool-calls
# ---------------------------------------------------------------------------


class TestCreateToolCall:
    async def test_create_tool_call_returns_201(self, client):
        await client.post("/api/reports", json=make_report_payload("rpt_tc"))
        resp = await client.post(
            "/api/reports/rpt_tc/tool-calls", json=make_tool_call_payload()
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["tool_name"] == "search_news"
        assert body["latency_ms"] == 450
        assert body["status"] == "success"

    async def test_create_tool_call_for_missing_report_returns_404(self, client):
        resp = await client.post(
            "/api/reports/rpt_ghost/tool-calls", json=make_tool_call_payload()
        )
        assert resp.status_code == 404

    async def test_create_tool_call_error_status(self, client):
        await client.post("/api/reports", json=make_report_payload("rpt_tc_err"))
        payload = make_tool_call_payload(status="error", latency_ms=200)
        resp = await client.post("/api/reports/rpt_tc_err/tool-calls", json=payload)
        assert resp.status_code == 201
        assert resp.json()["status"] == "error"


# ---------------------------------------------------------------------------
# GET /api/reports/{report_id}/tool-calls
# ---------------------------------------------------------------------------


class TestListToolCalls:
    async def test_list_tool_calls_returns_ordered_list(self, client):
        await client.post("/api/reports", json=make_report_payload("rpt_tcl"))
        for i in range(3):
            payload = make_tool_call_payload(tool_name=f"tool_{i}")
            payload["timestamp"] = f"2026-03-01T12:0{i}:00Z"
            await client.post("/api/reports/rpt_tcl/tool-calls", json=payload)

        resp = await client.get("/api/reports/rpt_tcl/tool-calls")
        assert resp.status_code == 200
        calls = resp.json()
        assert len(calls) == 3
        timestamps = [c["timestamp"] for c in calls]
        assert timestamps == sorted(timestamps)

    async def test_list_tool_calls_missing_report_returns_404(self, client):
        resp = await client.get("/api/reports/rpt_no_calls/tool-calls")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/reports/{report_id}/sources
# ---------------------------------------------------------------------------


class TestCreateSources:
    async def test_create_sources_returns_201_list(self, client):
        await client.post("/api/reports", json=make_report_payload("rpt_src"))
        payload = {
            "sources": [
                make_source_payload("https://a.com/1"),
                make_source_payload("https://a.com/2"),
            ]
        }
        resp = await client.post("/api/reports/rpt_src/sources", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert len(body) == 2
        urls = {s["url"] for s in body}
        assert "https://a.com/1" in urls

    async def test_create_sources_missing_report_returns_404(self, client):
        payload = {"sources": [make_source_payload()]}
        resp = await client.post("/api/reports/rpt_ghost_src/sources", json=payload)
        assert resp.status_code == 404

    async def test_create_sources_empty_list_returns_422(self, client):
        """An empty sources array should fail Pydantic min_length validation."""
        await client.post("/api/reports", json=make_report_payload("rpt_empty_src"))
        resp = await client.post("/api/reports/rpt_empty_src/sources", json={"sources": []})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/reports/{report_id}/sources
# ---------------------------------------------------------------------------


class TestListSources:
    async def test_list_sources(self, client):
        await client.post("/api/reports", json=make_report_payload("rpt_lsrc"))
        await client.post(
            "/api/reports/rpt_lsrc/sources",
            json={"sources": [make_source_payload("https://b.com/1")]},
        )
        resp = await client.get("/api/reports/rpt_lsrc/sources")
        assert resp.status_code == 200
        sources = resp.json()
        assert len(sources) == 1
        assert sources[0]["url"] == "https://b.com/1"

    async def test_list_sources_missing_report_returns_404(self, client):
        resp = await client.get("/api/reports/rpt_no_src/sources")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/metrics/tool-latency
# ---------------------------------------------------------------------------


class TestToolLatencyMetric:
    async def _seed_tool_calls(self, client, latencies: list[int]) -> None:
        await client.post("/api/reports", json=make_report_payload("rpt_metrics"))
        for i, ms in enumerate(latencies):
            payload = make_tool_call_payload(latency_ms=ms)
            payload["timestamp"] = f"2026-03-01T12:{i:02d}:00Z"
            await client.post("/api/reports/rpt_metrics/tool-calls", json=payload)

    async def test_tool_latency_with_data(self, client):
        await self._seed_tool_calls(client, [100, 200, 300, 400, 500])
        resp = await client.get("/api/metrics/tool-latency")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 5
        assert body["p50_ms"] is not None
        assert body["avg_ms"] == 300

    async def test_tool_latency_no_data(self, client):
        resp = await client.get("/api/metrics/tool-latency")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["p50_ms"] is None


# ---------------------------------------------------------------------------
# GET /api/metrics/error-rate
# ---------------------------------------------------------------------------


class TestErrorRateMetric:
    async def _seed_mixed(self, client) -> None:
        await client.post("/api/reports", json=make_report_payload("rpt_er"))
        # 2 success + 1 error
        for status, ms in [("success", 200), ("success", 300), ("error", 100)]:
            payload = make_tool_call_payload(tool_name="search_news", status=status, latency_ms=ms)
            await client.post("/api/reports/rpt_er/tool-calls", json=payload)

    async def test_error_rate_with_data(self, client):
        await self._seed_mixed(client)
        resp = await client.get("/api/metrics/error-rate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert body["errors"] == 1
        assert body["error_rate"] == pytest.approx(0.3333, abs=0.001)
        assert len(body["by_tool"]) == 1
        assert body["by_tool"][0]["tool_name"] == "search_news"

    async def test_error_rate_no_data(self, client):
        resp = await client.get("/api/metrics/error-rate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["error_rate"] == 0.0
        assert body["by_tool"] == []
