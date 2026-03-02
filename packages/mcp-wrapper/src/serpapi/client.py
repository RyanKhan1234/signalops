"""Async SerpApi HTTP client.

Handles request construction, time-range mapping, timeout enforcement, and
raw response parsing.  The API key is injected at construction time from the
``Config`` object and is never logged or returned in responses.

Time-range mapping
------------------
The MCP tool layer accepts human-friendly strings such as ``"7d"``.  This
client translates those into SerpApi ``tbs`` parameter values before making
the HTTP request.

| Input | SerpApi ``tbs`` |
|-------|-----------------|
| ``"1d"`` | ``qdr:d``       |
| ``"7d"`` | ``qdr:w``       |
| ``"30d"`` | ``qdr:m``      |
| ``"1y"`` | ``qdr:y``       |
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.serpapi.models import SerpApiResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TIME_RANGE_MAP: dict[str, str] = {
    "1d": "qdr:d",
    "7d": "qdr:w",
    "30d": "qdr:m",
    "1y": "qdr:y",
}

_DEFAULT_TIMEOUT_SECONDS: float = 10.0
_DEFAULT_GEOLOCATION: str = "us"


class SerpApiClient:
    """Async HTTP client for the SerpApi ``/search`` endpoint.

    Parameters
    ----------
    api_key:
        SerpApi API key — never logged or included in error responses.
    base_url:
        Override the default SerpApi endpoint (useful for testing).
    timeout:
        Per-request timeout in seconds (default 10 s).
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://serpapi.com/search",
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not api_key:
            raise ValueError("SERPAPI_API_KEY must not be empty")
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Context-manager helpers so callers can use ``async with``
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "SerpApiClient":
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @staticmethod
    def map_time_range(time_range: str) -> str:
        """Convert a human-friendly time range string to a SerpApi ``tbs`` value.

        Parameters
        ----------
        time_range:
            One of ``"1d"``, ``"7d"``, ``"30d"``, ``"1y"``.

        Returns
        -------
        str
            The corresponding SerpApi ``tbs`` parameter value.

        Raises
        ------
        ValueError
            If ``time_range`` is not a recognised value.
        """
        try:
            return _TIME_RANGE_MAP[time_range]
        except KeyError:
            valid = list(_TIME_RANGE_MAP.keys())
            raise ValueError(
                f"Unsupported time_range {time_range!r}. Must be one of {valid}."
            )

    # ------------------------------------------------------------------
    # Core request method
    # ------------------------------------------------------------------

    async def search_news(
        self,
        query: str,
        time_range: str = "7d",
        num_results: int = 10,
        gl: str = _DEFAULT_GEOLOCATION,
    ) -> SerpApiResponse:
        """Execute a Google News search via SerpApi.

        Parameters
        ----------
        query:
            The search query string.
        time_range:
            Human-friendly time range (``"1d"``, ``"7d"``, ``"30d"``, ``"1y"``).
        num_results:
            Number of results to request (1–50).
        gl:
            Geolocation code (default ``"us"``).

        Returns
        -------
        SerpApiResponse
            Parsed (but *not* normalised) SerpApi response.

        Raises
        ------
        httpx.TimeoutException
            If SerpApi does not respond within the configured timeout.
        httpx.HTTPError
            On any other HTTP-level failure.
        """
        tbs = self.map_time_range(time_range)
        params: dict[str, Any] = {
            "engine": "google_news",
            "q": query,
            "tbm": "nws",
            "tbs": tbs,
            "num": str(num_results),
            "gl": gl,
            "api_key": self._api_key,
        }

        logger.debug(
            "SerpApi request: engine=google_news q=%r tbs=%s num=%d",
            query,
            tbs,
            num_results,
        )

        client = self._get_client()
        response = await client.get(self._base_url, params=params)
        response.raise_for_status()

        raw: dict[str, Any] = response.json()

        # Log a redacted summary (never log the full response to avoid leaking data)
        result_count = len(raw.get("news_results") or [])
        logger.debug("SerpApi response: %d news_results returned", result_count)

        return SerpApiResponse.model_validate(raw)

    async def get_article_metadata(self, url: str) -> SerpApiResponse:
        """Search SerpApi for metadata about a specific article URL.

        Because SerpApi does not expose a dedicated metadata endpoint this
        method issues a news search using the URL as the query, which
        typically surfaces the canonical article near the top of results.

        Parameters
        ----------
        url:
            The article URL to look up.

        Returns
        -------
        SerpApiResponse
            Parsed SerpApi response.
        """
        params: dict[str, Any] = {
            "engine": "google_news",
            "q": url,
            "tbm": "nws",
            "num": "3",
            "gl": _DEFAULT_GEOLOCATION,
            "api_key": self._api_key,
        }

        logger.debug("SerpApi metadata request for URL: %r", url)

        client = self._get_client()
        response = await client.get(self._base_url, params=params)
        response.raise_for_status()

        raw: dict[str, Any] = response.json()
        return SerpApiResponse.model_validate(raw)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> httpx.AsyncClient:
        """Return the active ``httpx.AsyncClient``, creating one if necessary.

        Callers that do *not* use the async context manager get a lazily-created
        client.  This client is not closed automatically — prefer using
        ``async with SerpApiClient(...) as client:`` for proper resource cleanup.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client
