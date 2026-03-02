"""Pytest configuration and shared fixtures for the Traceability Store tests.

Uses an in-memory SQLite database via aiosqlite so no PostgreSQL instance is
required. The ORM models use ``FlexibleJSON`` which renders as JSON on SQLite
and JSONB on PostgreSQL, making the test setup transparent.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from src.api.app import create_app
from src.db.engine import get_session
from src.db.models import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Engine & session fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def engine():
    """Create a fresh in-memory SQLite engine for each test function."""
    _engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide an AsyncSession bound to the test engine."""
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess


# ---------------------------------------------------------------------------
# FastAPI test client fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def client(engine) -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx AsyncClient wired to a fresh test database."""
    app = create_app()

    # Build a session factory bound to the test engine
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as sess:
            yield sess

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Shared test data factories
# ---------------------------------------------------------------------------


def make_report_payload(
    report_id: str = "rpt_test001",
    digest_type: str = "weekly_report",
    query: str = "Anything important about Walmart Connect this week?",
) -> dict:
    """Build a valid CreateReportRequest payload."""
    return {
        "report_id": report_id,
        "digest_type": digest_type,
        "query": query,
        "digest_json": {
            "executive_summary": "Test summary",
            "key_signals": [],
            "risks": [],
            "opportunities": [],
            "action_items": [],
            "sources": [],
        },
        "generated_at": "2026-03-01T12:00:00Z",
        "user_id": "user_42",
    }


def make_tool_call_payload(
    tool_name: str = "search_news",
    status: str = "success",
    latency_ms: int = 450,
) -> dict:
    """Build a valid CreateToolCallRequest payload."""
    return {
        "tool_name": tool_name,
        "input_json": {"query": "Walmart Connect", "time_range": "7d"},
        "output_json": {"articles": [], "total_results": 0},
        "latency_ms": latency_ms,
        "status": status,
        "error_message": None if status == "success" else "Timeout reached",
        "timestamp": "2026-03-01T12:00:01Z",
    }


def make_source_payload(url: str = "https://example.com/article-1") -> dict:
    """Build a valid SourceItem payload."""
    return {
        "url": url,
        "title": "Walmart Connect Expands Self-Serve Platform",
        "source_name": "TechCrunch",
        "published_date": "2026-02-28T09:00:00Z",
        "snippet": "Walmart Connect announced new self-serve capabilities...",
        "accessed_at": "2026-03-01T12:00:00Z",
    }


UTC = timezone.utc


def now_utc() -> datetime:
    return datetime.now(UTC)
