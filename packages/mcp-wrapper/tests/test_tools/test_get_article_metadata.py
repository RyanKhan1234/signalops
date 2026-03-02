"""Tests for src/tools/get_article_metadata.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.middleware.cache import ResponseCache
from src.middleware.rate_limiter import RateLimiter
from src.serpapi.client import SerpApiClient
from src.serpapi.models import SerpApiResponse
from src.tools.get_article_metadata import execute_get_article_metadata
from tests.conftest import load_fixture

_VALID_URL = "https://www.retaildive.com/news/walmart-connect-self-serve-smb/123456/"


class TestGetArticleMetadataSuccess:
    """Test successful executions."""

    async def test_returns_normalized_response(
        self,
        mock_serpapi_client_metadata: SerpApiClient,
        metadata_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_get_article_metadata(
            url=_VALID_URL,
            client=mock_serpapi_client_metadata,
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )
        assert "articles" in result
        assert "cached" in result
        assert "request_id" in result

    async def test_url_stored_as_query(
        self,
        mock_serpapi_client_metadata: SerpApiClient,
        metadata_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_get_article_metadata(
            url=_VALID_URL,
            client=mock_serpapi_client_metadata,
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )
        assert result["query"] == _VALID_URL

    async def test_not_cached_on_first_call(
        self,
        mock_serpapi_client_metadata: SerpApiClient,
        metadata_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_get_article_metadata(
            url=_VALID_URL,
            client=mock_serpapi_client_metadata,
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )
        assert result["cached"] is False


class TestGetArticleMetadataCache:
    """Test caching for get_article_metadata."""

    async def test_second_call_returns_cached(
        self,
        mock_serpapi_client_metadata: SerpApiClient,
        metadata_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        await execute_get_article_metadata(
            url=_VALID_URL,
            client=mock_serpapi_client_metadata,
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )
        result2 = await execute_get_article_metadata(
            url=_VALID_URL,
            client=mock_serpapi_client_metadata,
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )
        assert result2["cached"] is True
        assert mock_serpapi_client_metadata.get_article_metadata.call_count == 1

    async def test_different_urls_different_cache_entries(
        self,
        mock_serpapi_client_metadata: SerpApiClient,
        metadata_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        await execute_get_article_metadata(
            url="https://example.com/article1",
            client=mock_serpapi_client_metadata,
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )
        await execute_get_article_metadata(
            url="https://example.com/article2",
            client=mock_serpapi_client_metadata,
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )
        assert mock_serpapi_client_metadata.get_article_metadata.call_count == 2


class TestGetArticleMetadataValidation:
    """Test input validation."""

    async def test_empty_url_returns_validation_error(
        self,
        mock_serpapi_client_metadata: SerpApiClient,
        metadata_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_get_article_metadata(
            url="",
            client=mock_serpapi_client_metadata,
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )
        assert result["error"]["code"] == "VALIDATION_ERROR"
        mock_serpapi_client_metadata.get_article_metadata.assert_not_called()

    async def test_invalid_url_returns_validation_error(
        self,
        mock_serpapi_client_metadata: SerpApiClient,
        metadata_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_get_article_metadata(
            url="not-a-valid-url",
            client=mock_serpapi_client_metadata,
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )
        assert result["error"]["code"] == "VALIDATION_ERROR"

    async def test_ftp_url_returns_validation_error(
        self,
        mock_serpapi_client_metadata: SerpApiClient,
        metadata_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        result = await execute_get_article_metadata(
            url="ftp://example.com/article",
            client=mock_serpapi_client_metadata,
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )
        assert result["error"]["code"] == "VALIDATION_ERROR"


class TestGetArticleMetadataRateLimit:
    """Test rate limiting for get_article_metadata."""

    async def test_rate_limit_exceeded_returns_error(
        self,
        mock_serpapi_client_metadata: SerpApiClient,
        metadata_cache: ResponseCache,
        tight_rate_limiter: RateLimiter,
    ) -> None:
        await execute_get_article_metadata(
            url="https://example.com/a1",
            client=mock_serpapi_client_metadata,
            cache=metadata_cache,
            rate_limiter=tight_rate_limiter,
        )
        await execute_get_article_metadata(
            url="https://example.com/a2",
            client=mock_serpapi_client_metadata,
            cache=metadata_cache,
            rate_limiter=tight_rate_limiter,
        )
        result = await execute_get_article_metadata(
            url="https://example.com/a3",
            client=mock_serpapi_client_metadata,
            cache=metadata_cache,
            rate_limiter=tight_rate_limiter,
        )
        assert result["error"]["code"] == "RATE_LIMIT_EXCEEDED"


class TestGetArticleMetadataUpstreamErrors:
    """Test upstream error handling for get_article_metadata."""

    async def test_timeout_returns_upstream_timeout(
        self,
        metadata_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        client = MagicMock(spec=SerpApiClient)
        client.get_article_metadata = AsyncMock(
            side_effect=httpx.ReadTimeout("timeout", request=MagicMock())
        )
        result = await execute_get_article_metadata(
            url=_VALID_URL,
            client=client,
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )
        assert result["error"]["code"] == "UPSTREAM_TIMEOUT"

    async def test_http_error_returns_upstream_error(
        self,
        metadata_cache: ResponseCache,
        rate_limiter: RateLimiter,
    ) -> None:
        request = httpx.Request("GET", "https://serpapi.com/search")
        response = httpx.Response(500, request=request)
        exc = httpx.HTTPStatusError("Server Error", request=request, response=response)

        client = MagicMock(spec=SerpApiClient)
        client.get_article_metadata = AsyncMock(side_effect=exc)

        result = await execute_get_article_metadata(
            url=_VALID_URL,
            client=client,
            cache=metadata_cache,
            rate_limiter=rate_limiter,
        )
        assert result["error"]["code"] == "UPSTREAM_ERROR"
