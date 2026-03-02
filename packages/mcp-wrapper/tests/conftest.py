"""Shared pytest fixtures for the MCP Wrapper test suite."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.middleware.cache import ResponseCache
from src.middleware.rate_limiter import RateLimiter
from src.serpapi.client import SerpApiClient
from src.serpapi.models import SerpApiResponse

# ---------------------------------------------------------------------------
# Fixture directory helper
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> dict[str, Any]:
    """Load a JSON fixture file and return it as a dict."""
    path = FIXTURES_DIR / filename
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Environment setup
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def set_serpapi_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure SERPAPI_API_KEY is always set for tests."""
    monkeypatch.setenv("SERPAPI_API_KEY", "test-api-key-12345")


# ---------------------------------------------------------------------------
# Infrastructure fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def news_cache() -> ResponseCache:
    """Fresh ResponseCache with 15-minute TTL for each test."""
    return ResponseCache(ttl_seconds=900)


@pytest.fixture()
def metadata_cache() -> ResponseCache:
    """Fresh ResponseCache with 1-hour TTL for each test."""
    return ResponseCache(ttl_seconds=3600)


@pytest.fixture()
def rate_limiter() -> RateLimiter:
    """Fresh RateLimiter with generous limits for each test."""
    return RateLimiter(per_minute=30, per_day=1000)


@pytest.fixture()
def tight_rate_limiter() -> RateLimiter:
    """RateLimiter with very tight limits for rate-limit enforcement tests."""
    return RateLimiter(per_minute=2, per_day=5)


# ---------------------------------------------------------------------------
# SerpApi fixture responses
# ---------------------------------------------------------------------------


@pytest.fixture()
def serpapi_news_fixture() -> dict[str, Any]:
    return load_fixture("serpapi_news_response.json")


@pytest.fixture()
def serpapi_empty_fixture() -> dict[str, Any]:
    return load_fixture("serpapi_empty_response.json")


@pytest.fixture()
def serpapi_metadata_fixture() -> dict[str, Any]:
    return load_fixture("serpapi_metadata_response.json")


@pytest.fixture()
def serpapi_duplicate_fixture() -> dict[str, Any]:
    return load_fixture("serpapi_duplicate_response.json")


# ---------------------------------------------------------------------------
# Mock SerpApiClient
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_serpapi_client(serpapi_news_fixture: dict[str, Any]) -> SerpApiClient:
    """SerpApiClient whose ``search_news`` returns the standard news fixture."""
    client = MagicMock(spec=SerpApiClient)
    client.search_news = AsyncMock(
        return_value=SerpApiResponse.model_validate(serpapi_news_fixture)
    )
    client.get_article_metadata = AsyncMock(
        return_value=SerpApiResponse.model_validate(serpapi_news_fixture)
    )
    return client


@pytest.fixture()
def mock_serpapi_client_empty(serpapi_empty_fixture: dict[str, Any]) -> SerpApiClient:
    """SerpApiClient that returns an empty result set."""
    client = MagicMock(spec=SerpApiClient)
    client.search_news = AsyncMock(
        return_value=SerpApiResponse.model_validate(serpapi_empty_fixture)
    )
    client.get_article_metadata = AsyncMock(
        return_value=SerpApiResponse.model_validate(serpapi_empty_fixture)
    )
    return client


@pytest.fixture()
def mock_serpapi_client_metadata(serpapi_metadata_fixture: dict[str, Any]) -> SerpApiClient:
    """SerpApiClient that returns metadata fixture."""
    client = MagicMock(spec=SerpApiClient)
    client.get_article_metadata = AsyncMock(
        return_value=SerpApiResponse.model_validate(serpapi_metadata_fixture)
    )
    client.search_news = AsyncMock(
        return_value=SerpApiResponse.model_validate(serpapi_metadata_fixture)
    )
    return client


@pytest.fixture()
def mock_serpapi_client_duplicate(serpapi_duplicate_fixture: dict[str, Any]) -> SerpApiClient:
    """SerpApiClient that returns the duplicate fixture."""
    client = MagicMock(spec=SerpApiClient)
    client.search_news = AsyncMock(
        return_value=SerpApiResponse.model_validate(serpapi_duplicate_fixture)
    )
    client.get_article_metadata = AsyncMock(
        return_value=SerpApiResponse.model_validate(serpapi_duplicate_fixture)
    )
    return client
