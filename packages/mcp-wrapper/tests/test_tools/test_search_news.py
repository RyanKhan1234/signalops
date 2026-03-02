"""Tests for src/tools/search_news.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.middleware.cache import ResponseCache
from src.middleware.rate_limiter import RateLimiter
from src.serpapi.client import SerpApiClient
from src.serpapi.models import SerpApiResponse
from src.tools.search_news import execute_search_news
from tests.conftest import load_fixture


class TestSearchNewsSuccess:
    """Test successful search_news executions."""

    async def test_returns_normalized_articles(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_search_news(
            query="Walmart Connect",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert "articles" in result
        assert "request_id" in result
        assert "cached" in result
        assert result["cached"] is False
        assert len(result["articles"]) == 3

    async def test_articles_have_correct_schema(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_search_news(
            query="Walmart Connect",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        article = result["articles"][0]
        assert "title" in article
        assert "url" in article
        assert "source" in article
        assert "published_date" in article
        assert "snippet" in article
        assert "thumbnail_url" in article

    async def test_query_preserved_in_response(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_search_news(
            query="Walmart Connect retail media",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert result["query"] == "Walmart Connect retail media"

    async def test_default_time_range_is_7d(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        await execute_search_news(
            query="test",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        mock_serpapi_client.search_news.assert_called_once()
        call_kwargs = mock_serpapi_client.search_news.call_args
        assert call_kwargs.kwargs.get("time_range", "7d") == "7d"


class TestSearchNewsCache:
    """Test caching behaviour."""

    async def test_second_call_returns_cached(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        # First call
        result1 = await execute_search_news(
            query="Walmart Connect",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        # Second call — should hit cache
        result2 = await execute_search_news(
            query="Walmart Connect",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )

        assert result2["cached"] is True
        # SerpApi should have been called only once
        assert mock_serpapi_client.search_news.call_count == 1

    async def test_different_queries_are_separate_cache_entries(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        await execute_search_news(
            query="Walmart Connect",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        await execute_search_news(
            query="Amazon Advertising",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert mock_serpapi_client.search_news.call_count == 2


class TestSearchNewsValidation:
    """Test that invalid inputs are rejected before calling SerpApi."""

    async def test_empty_query_returns_validation_error(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_search_news(
            query="",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert "error" in result
        assert result["error"]["code"] == "VALIDATION_ERROR"
        # SerpApi must NOT have been called
        mock_serpapi_client.search_news.assert_not_called()

    async def test_invalid_time_range_returns_validation_error(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_search_news(
            query="valid query",
            time_range="5d",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert "error" in result
        assert result["error"]["code"] == "VALIDATION_ERROR"

    async def test_num_results_out_of_range_returns_error(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_search_news(
            query="valid query",
            num_results=100,
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert "error" in result
        assert result["error"]["code"] == "VALIDATION_ERROR"


class TestSearchNewsRateLimit:
    """Test rate limit enforcement."""

    async def test_rate_limit_exceeded_returns_error(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        tight_rate_limiter: RateLimiter,
    ) -> None:
        # Exhaust the tight rate limiter (2 per minute)
        await execute_search_news(
            query="query one",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=tight_rate_limiter,
        )
        await execute_search_news(
            query="query two",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=tight_rate_limiter,
        )

        result = await execute_search_news(
            query="query three",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=tight_rate_limiter,
        )
        assert "error" in result
        assert result["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert result["error"]["retry_after_seconds"] >= 1

    async def test_rate_limit_error_not_cached(
        self,
        mock_serpapi_client: SerpApiClient,
        news_cache: ResponseCache,
        tight_rate_limiter: RateLimiter,
    ) -> None:
        """Rate limit errors should not be stored in the cache."""
        tight_rate_limiter.check()  # 1
        tight_rate_limiter.check()  # 2 — exhausted
        # This should fail with rate limit
        await execute_search_news(
            query="q",
            client=mock_serpapi_client,
            cache=news_cache,
            rate_limiter=tight_rate_limiter,
        )
        assert news_cache.size == 0


class TestSearchNewsUpstreamErrors:
    """Test upstream error handling."""

    async def test_serpapi_timeout_returns_upstream_timeout(
        self,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        client = MagicMock(spec=SerpApiClient)
        client.search_news = AsyncMock(
            side_effect=httpx.ReadTimeout("timeout", request=MagicMock())
        )
        result = await execute_search_news(
            query="Walmart Connect",
            client=client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert result["error"]["code"] == "UPSTREAM_TIMEOUT"

    async def test_serpapi_http_error_returns_upstream_error(
        self,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        request = httpx.Request("GET", "https://serpapi.com/search")
        response = httpx.Response(502, request=request)
        exc = httpx.HTTPStatusError("Bad Gateway", request=request, response=response)

        client = MagicMock(spec=SerpApiClient)
        client.search_news = AsyncMock(side_effect=exc)

        result = await execute_search_news(
            query="Walmart Connect",
            client=client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert result["error"]["code"] == "UPSTREAM_ERROR"

    async def test_unexpected_exception_returns_internal_error(
        self,
        news_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        client = MagicMock(spec=SerpApiClient)
        client.search_news = AsyncMock(side_effect=RuntimeError("Unexpected!"))

        result = await execute_search_news(
            query="Walmart Connect",
            client=client,
            cache=news_cache,
            rate_limiter=rate_limiter,
        )
        assert result["error"]["code"] == "INTERNAL_ERROR"
