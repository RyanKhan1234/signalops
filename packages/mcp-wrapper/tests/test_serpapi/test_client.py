"""Tests for src/serpapi/client.py."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from src.serpapi.client import SerpApiClient
from src.serpapi.models import SerpApiResponse
from tests.conftest import load_fixture


class TestTimeRangeMapping:
    """Test the time-range mapping helper."""

    def test_1d_maps_to_qdr_d(self) -> None:
        assert SerpApiClient.map_time_range("1d") == "qdr:d"

    def test_7d_maps_to_qdr_w(self) -> None:
        assert SerpApiClient.map_time_range("7d") == "qdr:w"

    def test_30d_maps_to_qdr_m(self) -> None:
        assert SerpApiClient.map_time_range("30d") == "qdr:m"

    def test_1y_maps_to_qdr_y(self) -> None:
        assert SerpApiClient.map_time_range("1y") == "qdr:y"

    def test_invalid_range_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unsupported time_range"):
            SerpApiClient.map_time_range("5d")


class TestSerpApiClientInit:
    """Test client initialisation."""

    def test_empty_api_key_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="SERPAPI_API_KEY must not be empty"):
            SerpApiClient(api_key="")

    def test_valid_init(self) -> None:
        client = SerpApiClient(api_key="test-key")
        assert client is not None


class TestSerpApiClientSearchNews:
    """Test the search_news method with mocked HTTP responses."""

    @respx.mock
    async def test_search_news_returns_parsed_response(self) -> None:
        fixture = load_fixture("serpapi_news_response.json")
        respx.get("https://serpapi.com/search").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        async with SerpApiClient(api_key="test-key") as client:
            result = await client.search_news(
                query="Walmart Connect", time_range="7d", num_results=10
            )

        assert isinstance(result, SerpApiResponse)
        assert result.news_results is not None
        assert len(result.news_results) == 3

    @respx.mock
    async def test_search_news_sends_correct_params(self) -> None:
        fixture = load_fixture("serpapi_news_response.json")
        route = respx.get("https://serpapi.com/search").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        async with SerpApiClient(api_key="test-key") as client:
            await client.search_news(query="test query", time_range="1d", num_results=5)

        assert route.called
        request = route.calls[0].request
        params = dict(httpx.QueryParams(request.url.query))
        assert params["q"] == "test query"
        assert params["tbs"] == "qdr:d"
        assert params["num"] == "5"
        assert params["engine"] == "google_news"
        # tbm=nws must NOT be present — it conflicts with engine=google_news (D3 fix)
        assert "tbm" not in params
        # API key must be in params but let's not assert its value in logs
        assert "api_key" in params

    @respx.mock
    async def test_search_news_raises_on_http_error(self) -> None:
        respx.get("https://serpapi.com/search").mock(
            return_value=httpx.Response(403, json={"error": "Forbidden"})
        )

        async with SerpApiClient(api_key="test-key") as client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.search_news(query="test")

    @respx.mock
    async def test_search_news_raises_on_timeout(self) -> None:
        respx.get("https://serpapi.com/search").mock(
            side_effect=httpx.ReadTimeout("Timed out", request=MagicMock())
        )

        async with SerpApiClient(api_key="test-key") as client:
            with pytest.raises(httpx.TimeoutException):
                await client.search_news(query="test")

    @respx.mock
    async def test_get_article_metadata_returns_parsed_response(self) -> None:
        fixture = load_fixture("serpapi_metadata_response.json")
        respx.get("https://serpapi.com/search").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        async with SerpApiClient(api_key="test-key") as client:
            result = await client.get_article_metadata(
                url="https://www.retaildive.com/news/walmart-connect-self-serve-smb/123456/"
            )

        assert isinstance(result, SerpApiResponse)
        assert result.news_results is not None

    @respx.mock
    async def test_client_custom_base_url(self) -> None:
        fixture = load_fixture("serpapi_news_response.json")
        respx.get("https://custom.serpapi.example.com/search").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        async with SerpApiClient(
            api_key="test-key",
            base_url="https://custom.serpapi.example.com/search",
        ) as client:
            result = await client.search_news(query="test")

        assert result is not None
