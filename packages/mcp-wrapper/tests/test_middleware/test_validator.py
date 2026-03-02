"""Tests for src/middleware/validator.py."""

from __future__ import annotations

import pytest

from src.middleware.validator import (
    validate_company,
    validate_get_article_metadata_inputs,
    validate_num_results,
    validate_query,
    validate_search_company_news_inputs,
    validate_search_news_inputs,
    validate_time_range,
    validate_topics,
    validate_url,
)


# ---------------------------------------------------------------------------
# validate_query
# ---------------------------------------------------------------------------


class TestValidateQuery:
    def test_valid_query(self) -> None:
        assert validate_query("Walmart Connect retail media") is None

    def test_empty_string_fails(self) -> None:
        error = validate_query("")
        assert error is not None
        assert error.field == "query"
        assert error.constraint == "non_empty"

    def test_whitespace_only_fails(self) -> None:
        error = validate_query("   ")
        assert error is not None
        assert error.constraint == "non_empty"

    def test_none_fails(self) -> None:
        error = validate_query(None)
        assert error is not None
        assert error.constraint == "non_empty"

    def test_too_long_fails(self) -> None:
        error = validate_query("x" * 201)
        assert error is not None
        assert "max_length" in error.constraint

    def test_exactly_200_chars_passes(self) -> None:
        assert validate_query("x" * 200) is None

    def test_injection_lt_gt_fails(self) -> None:
        error = validate_query("query <script>")
        assert error is not None
        assert error.constraint == "no_injection_chars"

    def test_injection_braces_fails(self) -> None:
        error = validate_query("query {malicious}")
        assert error is not None
        assert error.constraint == "no_injection_chars"

    def test_injection_null_byte_fails(self) -> None:
        error = validate_query("query\x00")
        assert error is not None
        assert error.constraint == "no_injection_chars"


# ---------------------------------------------------------------------------
# validate_company
# ---------------------------------------------------------------------------


class TestValidateCompany:
    def test_valid_company(self) -> None:
        assert validate_company("Walmart Connect") is None

    def test_empty_fails(self) -> None:
        error = validate_company("")
        assert error is not None
        assert error.field == "company"

    def test_injection_fails(self) -> None:
        error = validate_company("Company<Name>")
        assert error is not None


# ---------------------------------------------------------------------------
# validate_time_range
# ---------------------------------------------------------------------------


class TestValidateTimeRange:
    def test_1d_valid(self) -> None:
        assert validate_time_range("1d") is None

    def test_7d_valid(self) -> None:
        assert validate_time_range("7d") is None

    def test_30d_valid(self) -> None:
        assert validate_time_range("30d") is None

    def test_1y_valid(self) -> None:
        assert validate_time_range("1y") is None

    def test_none_is_valid_optional(self) -> None:
        assert validate_time_range(None) is None

    def test_invalid_value_fails(self) -> None:
        error = validate_time_range("5d")
        assert error is not None
        assert error.field == "time_range"

    def test_invalid_string_fails(self) -> None:
        error = validate_time_range("weekly")
        assert error is not None


# ---------------------------------------------------------------------------
# validate_num_results
# ---------------------------------------------------------------------------


class TestValidateNumResults:
    def test_valid_10(self) -> None:
        assert validate_num_results(10) is None

    def test_valid_1(self) -> None:
        assert validate_num_results(1) is None

    def test_valid_50(self) -> None:
        assert validate_num_results(50) is None

    def test_none_is_valid_optional(self) -> None:
        assert validate_num_results(None) is None

    def test_zero_fails(self) -> None:
        error = validate_num_results(0)
        assert error is not None
        assert "range" in error.constraint

    def test_51_fails(self) -> None:
        error = validate_num_results(51)
        assert error is not None

    def test_negative_fails(self) -> None:
        error = validate_num_results(-1)
        assert error is not None

    def test_bool_fails(self) -> None:
        # bool is a subclass of int in Python but should be rejected
        error = validate_num_results(True)  # type: ignore[arg-type]
        assert error is not None
        assert error.constraint == "type:integer"


# ---------------------------------------------------------------------------
# validate_topics
# ---------------------------------------------------------------------------


class TestValidateTopics:
    def test_valid_topics(self) -> None:
        assert validate_topics(["ad platform", "partnerships"]) is None

    def test_none_is_valid_optional(self) -> None:
        assert validate_topics(None) is None

    def test_empty_list_is_valid(self) -> None:
        assert validate_topics([]) is None

    def test_not_a_list_fails(self) -> None:
        error = validate_topics("not a list")  # type: ignore[arg-type]
        assert error is not None
        assert "type:list" in error.constraint

    def test_empty_topic_fails(self) -> None:
        error = validate_topics(["valid", ""])
        assert error is not None

    def test_too_long_topic_fails(self) -> None:
        error = validate_topics(["x" * 101])
        assert error is not None

    def test_exactly_100_chars_passes(self) -> None:
        assert validate_topics(["x" * 100]) is None

    def test_injection_in_topic_fails(self) -> None:
        error = validate_topics(["<script>alert(1)</script>"])
        assert error is not None


# ---------------------------------------------------------------------------
# validate_url
# ---------------------------------------------------------------------------


class TestValidateUrl:
    def test_valid_https_url(self) -> None:
        assert validate_url("https://www.retaildive.com/news/article/123/") is None

    def test_valid_http_url(self) -> None:
        assert validate_url("http://example.com/article") is None

    def test_none_fails(self) -> None:
        error = validate_url(None)
        assert error is not None
        assert error.field == "url"

    def test_empty_fails(self) -> None:
        error = validate_url("")
        assert error is not None

    def test_ftp_scheme_fails(self) -> None:
        error = validate_url("ftp://example.com/article")
        assert error is not None
        assert "http_or_https" in error.constraint

    def test_no_host_fails(self) -> None:
        error = validate_url("https://")
        assert error is not None

    def test_no_scheme_fails(self) -> None:
        error = validate_url("example.com/article")
        assert error is not None


# ---------------------------------------------------------------------------
# Composite validators
# ---------------------------------------------------------------------------


class TestCompositeValidators:
    def test_search_news_all_valid(self) -> None:
        errors = validate_search_news_inputs("valid query", "7d", 10)
        assert errors == []

    def test_search_news_multiple_errors(self) -> None:
        errors = validate_search_news_inputs("", "bad_range", 0)
        assert len(errors) >= 3

    def test_search_company_news_all_valid(self) -> None:
        errors = validate_search_company_news_inputs(
            "Walmart", "30d", ["ads", "earnings"]
        )
        assert errors == []

    def test_search_company_news_company_error(self) -> None:
        errors = validate_search_company_news_inputs("", "7d")
        assert len(errors) >= 1
        assert errors[0].field == "company"

    def test_get_article_metadata_valid_url(self) -> None:
        errors = validate_get_article_metadata_inputs(
            "https://example.com/article"
        )
        assert errors == []

    def test_get_article_metadata_invalid_url(self) -> None:
        errors = validate_get_article_metadata_inputs("not-a-url")
        assert len(errors) >= 1
