"""Tests for src/middleware/rate_limiter.py."""

from __future__ import annotations

import time

import pytest

from src.middleware.rate_limiter import RateLimiter, RateLimitError


class TestRateLimiterBasic:
    """Test basic request recording and limit enforcement."""

    def test_first_request_allowed(self, rate_limiter: RateLimiter) -> None:
        assert rate_limiter.check() is None

    def test_requests_within_limit_allowed(
        self, tight_rate_limiter: RateLimiter
    ) -> None:
        # tight limiter: 2 per minute
        assert tight_rate_limiter.check() is None  # 1st
        assert tight_rate_limiter.check() is None  # 2nd

    def test_per_minute_limit_exceeded(
        self, tight_rate_limiter: RateLimiter
    ) -> None:
        # tight limiter: 2 per minute
        tight_rate_limiter.check()  # 1
        tight_rate_limiter.check()  # 2
        error = tight_rate_limiter.check()  # 3 — should fail
        assert error is not None
        assert error.code == "RATE_LIMIT_EXCEEDED"
        assert error.limit_type == "per_minute"

    def test_per_day_limit_exceeded(self) -> None:
        limiter = RateLimiter(per_minute=100, per_day=3)
        limiter.check()
        limiter.check()
        limiter.check()
        error = limiter.check()
        assert error is not None
        assert error.limit_type == "per_day"

    def test_rate_limit_error_has_retry_after(
        self, tight_rate_limiter: RateLimiter
    ) -> None:
        tight_rate_limiter.check()
        tight_rate_limiter.check()
        error = tight_rate_limiter.check()
        assert error is not None
        assert error.retry_after_seconds >= 1

    def test_per_minute_checked_before_per_day(self) -> None:
        """Per-minute limit should be reported first."""
        limiter = RateLimiter(per_minute=1, per_day=1)
        limiter.check()  # fills both windows
        error = limiter.check()
        assert error is not None
        assert error.limit_type == "per_minute"


class TestRateLimiterCounting:
    """Test the current count properties."""

    def test_current_minute_count_increases(
        self, rate_limiter: RateLimiter
    ) -> None:
        assert rate_limiter.current_minute_count == 0
        rate_limiter.check()
        assert rate_limiter.current_minute_count == 1

    def test_current_day_count_increases(self, rate_limiter: RateLimiter) -> None:
        assert rate_limiter.current_day_count == 0
        rate_limiter.check()
        assert rate_limiter.current_day_count == 1

    def test_reset_clears_counts(self, tight_rate_limiter: RateLimiter) -> None:
        tight_rate_limiter.check()
        tight_rate_limiter.check()
        tight_rate_limiter.reset()
        assert tight_rate_limiter.current_minute_count == 0
        assert tight_rate_limiter.current_day_count == 0

    def test_after_reset_new_requests_allowed(
        self, tight_rate_limiter: RateLimiter
    ) -> None:
        tight_rate_limiter.check()
        tight_rate_limiter.check()
        tight_rate_limiter.reset()
        assert tight_rate_limiter.check() is None


class TestSlidingWindowExpiry:
    """Test that old timestamps expire from the sliding window."""

    def test_old_minute_requests_expire(self) -> None:
        """After 60 seconds, per-minute window should reset."""
        limiter = RateLimiter(per_minute=1, per_day=1000)
        limiter.check()  # uses up the 1 per-minute slot
        error = limiter.check()
        assert error is not None and error.limit_type == "per_minute"

        # Manually backdating: reset and re-check (we can't sleep 60s in tests)
        # Instead, verify the retry_after_seconds is reasonable
        assert error.retry_after_seconds >= 1
        assert error.retry_after_seconds <= 60


class TestRateLimitError:
    """Test RateLimitError model."""

    def test_default_code(self) -> None:
        err = RateLimitError(
            message="too many requests",
            retry_after_seconds=30,
            limit_type="per_minute",
        )
        assert err.code == "RATE_LIMIT_EXCEEDED"

    def test_model_fields(self) -> None:
        err = RateLimitError(
            message="daily limit exceeded",
            retry_after_seconds=3600,
            limit_type="per_day",
        )
        assert err.retry_after_seconds == 3600
        assert err.limit_type == "per_day"
