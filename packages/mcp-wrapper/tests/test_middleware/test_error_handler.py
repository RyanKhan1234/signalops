"""Tests for src/middleware/error_handler.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from src.middleware.error_handler import (
    internal_error_response,
    rate_limit_error_response,
    upstream_error_response,
    upstream_timeout_response,
    validation_error_response,
)
from src.middleware.validator import ValidationError


class TestValidationErrorResponse:
    def test_code_is_validation_error(self) -> None:
        errors = [
            ValidationError(
                message="query is empty",
                field="query",
                constraint="non_empty",
            )
        ]
        result = validation_error_response(errors)
        assert result["error"]["code"] == "VALIDATION_ERROR"

    def test_message_from_first_error(self) -> None:
        errors = [
            ValidationError(message="first error", field="query", constraint="non_empty"),
            ValidationError(message="second error", field="time_range", constraint="one_of"),
        ]
        result = validation_error_response(errors)
        assert result["error"]["message"] == "first error"

    def test_details_contains_all_errors(self) -> None:
        errors = [
            ValidationError(message="e1", field="query", constraint="non_empty"),
            ValidationError(message="e2", field="num_results", constraint="range:1-50"),
        ]
        result = validation_error_response(errors)
        details = result["error"]["details"]["validation_errors"]
        assert len(details) == 2

    def test_no_retry_after(self) -> None:
        errors = [ValidationError(message="err", field="f", constraint="c")]
        result = validation_error_response(errors)
        assert result["error"]["retry_after_seconds"] is None


class TestRateLimitErrorResponse:
    def test_code_is_rate_limit_exceeded(self) -> None:
        result = rate_limit_error_response(30, "per_minute")
        assert result["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    def test_retry_after_seconds_preserved(self) -> None:
        result = rate_limit_error_response(3600, "per_day")
        assert result["error"]["retry_after_seconds"] == 3600

    def test_limit_type_in_details(self) -> None:
        result = rate_limit_error_response(30, "per_minute")
        assert result["error"]["details"]["limit_type"] == "per_minute"

    def test_message_contains_limit_type(self) -> None:
        result = rate_limit_error_response(30, "per_day")
        assert "per day" in result["error"]["message"]


class TestUpstreamErrorResponse:
    def _make_http_status_error(self, status_code: int) -> httpx.HTTPStatusError:
        request = httpx.Request("GET", "https://serpapi.com/search")
        response = httpx.Response(status_code, request=request)
        return httpx.HTTPStatusError(
            f"HTTP {status_code}", request=request, response=response
        )

    def test_code_is_upstream_error(self) -> None:
        exc = self._make_http_status_error(502)
        result = upstream_error_response(exc)
        assert result["error"]["code"] == "UPSTREAM_ERROR"

    def test_http_status_in_details(self) -> None:
        exc = self._make_http_status_error(403)
        result = upstream_error_response(exc)
        assert result["error"]["details"]["http_status"] == 403

    def test_request_id_in_details_when_provided(self) -> None:
        exc = self._make_http_status_error(500)
        result = upstream_error_response(exc, request_id="req-123")
        assert result["error"]["details"]["request_id"] == "req-123"

    def test_no_retry_after(self) -> None:
        exc = self._make_http_status_error(500)
        result = upstream_error_response(exc)
        assert result["error"]["retry_after_seconds"] is None


class TestUpstreamTimeoutResponse:
    def test_code_is_upstream_timeout(self) -> None:
        exc = httpx.ReadTimeout("Timed out", request=MagicMock())
        result = upstream_timeout_response(exc)
        assert result["error"]["code"] == "UPSTREAM_TIMEOUT"

    def test_exception_type_in_details(self) -> None:
        exc = httpx.ConnectTimeout("Timed out", request=MagicMock())
        result = upstream_timeout_response(exc)
        assert result["error"]["details"]["exception_type"] == "ConnectTimeout"

    def test_request_id_in_details_when_provided(self) -> None:
        exc = httpx.ReadTimeout("Timed out", request=MagicMock())
        result = upstream_timeout_response(exc, request_id="req-456")
        assert result["error"]["details"]["request_id"] == "req-456"


class TestInternalErrorResponse:
    def test_code_is_internal_error(self) -> None:
        exc = RuntimeError("Unexpected crash")
        result = internal_error_response(exc)
        assert result["error"]["code"] == "INTERNAL_ERROR"

    def test_exception_type_in_details(self) -> None:
        exc = ValueError("something went wrong")
        result = internal_error_response(exc)
        assert result["error"]["details"]["exception_type"] == "ValueError"

    def test_request_id_in_details_when_provided(self) -> None:
        exc = RuntimeError("crash")
        result = internal_error_response(exc, request_id="req-789")
        assert result["error"]["details"]["request_id"] == "req-789"
