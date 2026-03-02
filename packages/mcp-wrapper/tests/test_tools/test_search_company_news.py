"""Tests for src/tools/search_company_news.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.middleware.cache import ResponseCache
from src.middleware.rate_limiter import RateLimiter
from src.serpapi.client import SerpApiClient
from src.tools.search_company_news import _build_company_query, execute_search_company_news
from tests.conftest import load_fixture


class TestBuildCompanyQuery:
    """Test the company query builder."""

    def test_company_only(self) -> None:
        q = _build_company_query("Walmart Connect", None)
        assert q == "Walmart Connect"

    def test_company_with_topics(self) -> None:
        q = _build_company_query("Walmart Connect", ["ad platform", "earnings"])
        assert "Walmart Connect" in q
        assert "ad platform" in q
        assert "earnings" in q

    def test_empty_topics_list(self) -> None:
        q = _build_company_query("Apple", [])
        assert q == "Apple"


class TestSearchCompanyNewsSuccess:
    """Test successful executions."""

    async def test_returns_normalized_response(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_search_company_news(
            company="Walmart Connect",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert "articles" in result
        assert "cached" in result
        assert "request_id" in result

    async def test_company_only_no_topics(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_search_company_news(
            company="Walmart Connect",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert result.get("error") is None

    async def test_with_topics(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_search_company_news(
            company="Walmart Connect",
            topics=["retail media", "Q1 earnings"],
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert "articles" in result

    async def test_query_in_response_includes_company(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_search_company_news(
            company="Walmart Connect",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert "Walmart Connect" in result["query"]


class TestSearchCompanyNewsCache:
    """Test caching for search_company_news."""

    async def test_cache_hit_on_second_call(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        await execute_search_company_news(
            company="Walmart Connect",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        result2 = await execute_search_company_news(
            company="Walmart Connect",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert result2["cached"] is True
        assert mock_serpapi_client.search_news.call_count == 1

    async def test_different_topics_different_cache_entry(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        await execute_search_company_news(
            company="Walmart Connect",
            topics=["topic A"],
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        await execute_search_company_news(
            company="Walmart Connect",
            topics=["topic B"],
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert mock_serpapi_client.search_news.call_count == 2


class TestSearchCompanyNewsValidation:
    """Test validation for search_company_news."""

    async def test_empty_company_returns_validation_error(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_search_company_news(
            company="",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert result["error"]["code"] == "VALIDATION_ERROR"
        mock_serpapi_client.search_news.assert_not_called()

    async def test_invalid_time_range_returns_validation_error(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_search_company_news(
            company="Walmart",
            time_range="bad",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert result["error"]["code"] == "VALIDATION_ERROR"


class TestSearchCompanyNewsRateLimit:
    """Test rate limiting for search_company_news."""

    async def test_rate_limit_exceeded_returns_error(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        tight_rate_limiter: RateLimiter,
    ) -> None:
        await execute_search_company_news(
            company="Company A",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=tight_rate_limiter,
        )
        await execute_search_company_news(
            company="Company B",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=tight_rate_limiter,
        )
        result = await execute_search_company_news(
            company="Company C",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=tight_rate_limiter,
        )
        assert result["error"]["code"] == "RATE_LIMIT_EXCEEDED"


class TestSearchCompanyNewsUpstreamErrors:
    """Test upstream error handling for search_company_news."""

    async def test_timeout_returns_upstream_timeout(
        self,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        client = MagicMock(spec=SerpApiClient)
        client.search_news = AsyncMock(
            side_effect=httpx.ReadTimeout("timeout", request=MagicMock())
        )
        result = await execute_search_company_news(
            company="Walmart Connect",
            client=client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert result["error"]["code"] == "UPSTREAM_TIMEOUT"
