"""Tests for src/serpapi/normalizer.py."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest

from src.serpapi.models import NormalizedResponse, SerpApiResponse
from src.serpapi.normalizer import _parse_date, _strip_html, normalize_response
from tests.conftest import load_fixture

# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------


class TestParseDateRelative:
    """Test relative date parsing."""

    def test_hours_ago(self) -> None:
        result = _parse_date("2 hours ago")
        # Should be a valid ISO 8601 string
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", result)

    def test_days_ago(self) -> None:
        result = _parse_date("3 days ago")
        assert result.endswith("Z")

    def test_weeks_ago(self) -> None:
        result = _parse_date("1 week ago")
        assert result.endswith("Z")

    def test_minutes_ago(self) -> None:
        result = _parse_date("30 minutes ago")
        assert result.endswith("Z")

    def test_months_ago(self) -> None:
        result = _parse_date("2 months ago")
        assert result.endswith("Z")

    def test_years_ago(self) -> None:
        result = _parse_date("1 year ago")
        assert result.endswith("Z")

    def test_seconds_ago(self) -> None:
        result = _parse_date("45 seconds ago")
        assert result.endswith("Z")

    def test_plural_vs_singular(self) -> None:
        """'1 day ago' and '2 days ago' should both parse."""
        r1 = _parse_date("1 day ago")
        r2 = _parse_date("2 days ago")
        assert r1.endswith("Z")
        assert r2.endswith("Z")
        # 2 days ago should be earlier than 1 day ago
        assert r2 < r1


class TestParseDateAbsolute:
    """Test absolute date parsing."""

    def test_mar_01_2026(self) -> None:
        result = _parse_date("Mar 01, 2026")
        assert result.startswith("2026-03-01")

    def test_march_01_2026(self) -> None:
        result = _parse_date("March 01, 2026")
        assert result.startswith("2026-03-01")

    def test_iso_format(self) -> None:
        result = _parse_date("2026-03-01T12:00:00Z")
        assert result == "2026-03-01T12:00:00Z"

    def test_date_only(self) -> None:
        result = _parse_date("2026-03-01")
        assert result.startswith("2026-03-01")

    def test_none_returns_now(self) -> None:
        now = datetime.now(tz=timezone.utc)
        result = _parse_date(None)
        parsed_year = int(result[:4])
        assert parsed_year == now.year

    def test_unrecognised_falls_back_to_now(self) -> None:
        result = _parse_date("yesterday")
        # Should return current year as fallback
        now_year = datetime.now(tz=timezone.utc).year
        assert result.startswith(str(now_year))


# ---------------------------------------------------------------------------
# _strip_html
# ---------------------------------------------------------------------------


class TestStripHtml:
    """Test HTML entity stripping and tag removal."""

    def test_strips_amp(self) -> None:
        assert _strip_html("Walmart &amp; Roku") == "Walmart & Roku"

    def test_strips_apos(self) -> None:
        assert _strip_html("Walmart&#39;s") == "Walmart's"

    def test_strips_tags(self) -> None:
        assert _strip_html("<b>Bold</b> text") == "Bold text"

    def test_strips_em_tag(self) -> None:
        assert _strip_html("<em>important</em>") == "important"

    def test_empty_string(self) -> None:
        assert _strip_html("") == ""

    def test_none_returns_empty(self) -> None:
        assert _strip_html(None) == ""

    def test_plain_text_unchanged(self) -> None:
        assert _strip_html("Hello world") == "Hello world"


# ---------------------------------------------------------------------------
# normalize_response
# ---------------------------------------------------------------------------


class TestNormalizeResponse:
    """Test the main normalize_response function."""

    def test_returns_normalized_response(self) -> None:
        fixture = load_fixture("serpapi_news_response.json")
        raw = SerpApiResponse.model_validate(fixture)
        result = normalize_response(raw, query="Walmart Connect")

        assert isinstance(result, NormalizedResponse)
        assert result.query == "Walmart Connect"
        assert len(result.articles) == 3

    def test_html_entities_stripped_from_title(self) -> None:
        fixture = load_fixture("serpapi_news_response.json")
        raw = SerpApiResponse.model_validate(fixture)
        result = normalize_response(raw, query="test")

        # Second article has "Walmart &amp; Roku" in title
        titles = [a.title for a in result.articles]
        assert any("Walmart & Roku" in t for t in titles)

    def test_html_entities_stripped_from_snippet(self) -> None:
        fixture = load_fixture("serpapi_news_response.json")
        raw = SerpApiResponse.model_validate(fixture)
        result = normalize_response(raw, query="test")

        snippets = [a.snippet for a in result.articles]
        assert any("Walmart's" in s for s in snippets)

    def test_published_dates_are_iso_8601(self) -> None:
        fixture = load_fixture("serpapi_news_response.json")
        raw = SerpApiResponse.model_validate(fixture)
        result = normalize_response(raw, query="test")

        iso_pattern = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
        for article in result.articles:
            assert iso_pattern.match(article.published_date), (
                f"Date {article.published_date!r} is not ISO 8601"
            )

    def test_deduplicates_by_url(self) -> None:
        fixture = load_fixture("serpapi_duplicate_response.json")
        raw = SerpApiResponse.model_validate(fixture)
        result = normalize_response(raw, query="duplicate test")

        # 3 items in fixture with 2 sharing the same URL → 2 unique articles
        assert result.total_results == 2
        urls = [a.url for a in result.articles]
        assert len(urls) == len(set(urls))

    def test_generates_request_id_uuid(self) -> None:
        fixture = load_fixture("serpapi_news_response.json")
        raw = SerpApiResponse.model_validate(fixture)
        result = normalize_response(raw, query="test")

        # UUID4 format: 8-4-4-4-12
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )
        assert uuid_pattern.match(result.request_id), (
            f"request_id {result.request_id!r} is not a valid UUID4"
        )

    def test_uses_provided_request_id(self) -> None:
        fixture = load_fixture("serpapi_news_response.json")
        raw = SerpApiResponse.model_validate(fixture)
        result = normalize_response(raw, query="test", request_id="my-custom-id")
        assert result.request_id == "my-custom-id"

    def test_cached_flag_default_false(self) -> None:
        fixture = load_fixture("serpapi_news_response.json")
        raw = SerpApiResponse.model_validate(fixture)
        result = normalize_response(raw, query="test")
        assert result.cached is False

    def test_cached_flag_can_be_set_true(self) -> None:
        fixture = load_fixture("serpapi_news_response.json")
        raw = SerpApiResponse.model_validate(fixture)
        result = normalize_response(raw, query="test", cached=True)
        assert result.cached is True

    def test_empty_news_results(self) -> None:
        fixture = load_fixture("serpapi_empty_response.json")
        raw = SerpApiResponse.model_validate(fixture)
        result = normalize_response(raw, query="no results query")
        assert result.articles == []
        assert result.total_results == 0

    def test_total_results_matches_article_count(self) -> None:
        fixture = load_fixture("serpapi_news_response.json")
        raw = SerpApiResponse.model_validate(fixture)
        result = normalize_response(raw, query="test")
        assert result.total_results == len(result.articles)

    def test_thumbnail_url_preserved(self) -> None:
        fixture = load_fixture("serpapi_news_response.json")
        raw = SerpApiResponse.model_validate(fixture)
        result = normalize_response(raw, query="test")

        # First article has a thumbnail
        assert result.articles[0].thumbnail_url == "https://example.com/thumb1.jpg"

    def test_null_thumbnail_url_is_none(self) -> None:
        fixture = load_fixture("serpapi_news_response.json")
        raw = SerpApiResponse.model_validate(fixture)
        result = normalize_response(raw, query="test")

        # Third article has null thumbnail
        assert result.articles[2].thumbnail_url is None

    def test_articles_missing_url_skipped(self) -> None:
        """Articles without a URL should be excluded from normalised output."""
        raw_data = {
            "news_results": [
                {"title": "No URL article", "link": None, "source": "X", "date": "1 day ago", "snippet": "test"},
                {"title": "Has URL", "link": "https://example.com/valid", "source": "Y", "date": "1 day ago", "snippet": "test"},
            ]
        }
        raw = SerpApiResponse.model_validate(raw_data)
        result = normalize_response(raw, query="test")
        assert result.total_results == 1
        assert result.articles[0].url == "https://example.com/valid"
