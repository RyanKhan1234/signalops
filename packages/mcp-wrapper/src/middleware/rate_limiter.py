"""Sliding-window rate limiter for SerpApi quota protection.

Maintains two independent sliding windows:
* **Per-minute** — short burst protection (default 30 req/min).
* **Per-day** — daily quota protection (default 1 000 req/day).

Both windows use a simple timestamp-deque approach.  When a new request
arrives, timestamps older than the window are discarded before checking the
count.  This gives true sliding-window semantics without a scheduled cleanup
task.

Thread safety note
------------------
This implementation uses ``collections.deque`` which is not thread-safe for
concurrent coroutines.  For a high-concurrency deployment, wrap the ``check``
call with ``asyncio.Lock`` or migrate to an atomic Redis counter.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from datetime import datetime, timezone

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------


class RateLimitError(BaseModel):
    """Returned when a rate limit is exceeded."""

    code: str = "RATE_LIMIT_EXCEEDED"
    message: str
    retry_after_seconds: int
    limit_type: str  # "per_minute" or "per_day"


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Sliding-window rate limiter for two independent time windows.

    Parameters
    ----------
    per_minute:
        Maximum allowed requests per 60-second sliding window.
    per_day:
        Maximum allowed requests per 86 400-second sliding window.
    """

    _MINUTE_WINDOW: int = 60        # seconds
    _DAY_WINDOW: int = 86_400       # seconds

    def __init__(self, per_minute: int = 30, per_day: int = 1000) -> None:
        self._per_minute = per_minute
        self._per_day = per_day
        # Deques of UTC timestamps (as floats) for each window.
        self._minute_window: deque[float] = deque()
        self._day_window: deque[float] = deque()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def check(self) -> RateLimitError | None:
        """Check whether a new request is allowed.

        Prunes expired timestamps from both windows and then checks the
        current count against the configured limits.  If *both* windows are
        below their limits, the timestamp is recorded and ``None`` is returned.

        Returns
        -------
        RateLimitError | None
            A structured error if a limit is exceeded, ``None`` if allowed.
        """
        now = datetime.now(tz=timezone.utc).timestamp()
        self._prune(now)

        # Check per-minute first (smaller window → faster retry).
        if len(self._minute_window) >= self._per_minute:
            retry_after = self._retry_after_minute(now)
            logger.warning(
                "Per-minute rate limit exceeded (%d/%d); retry after %ds",
                len(self._minute_window),
                self._per_minute,
                retry_after,
            )
            return RateLimitError(
                message=(
                    f"Per-minute rate limit exceeded ({self._per_minute} req/min). "
                    f"Please retry after {retry_after} seconds."
                ),
                retry_after_seconds=retry_after,
                limit_type="per_minute",
            )

        if len(self._day_window) >= self._per_day:
            retry_after = self._retry_after_day(now)
            logger.warning(
                "Per-day rate limit exceeded (%d/%d); retry after %ds",
                len(self._day_window),
                self._per_day,
                retry_after,
            )
            return RateLimitError(
                message=(
                    f"Daily rate limit exceeded ({self._per_day} req/day). "
                    f"Please retry after {retry_after} seconds."
                ),
                retry_after_seconds=retry_after,
                limit_type="per_day",
            )

        # Record the request in both windows.
        self._minute_window.append(now)
        self._day_window.append(now)
        logger.debug(
            "Rate limit OK — per_minute=%d/%d per_day=%d/%d",
            len(self._minute_window),
            self._per_minute,
            len(self._day_window),
            self._per_day,
        )
        return None

    @property
    def current_minute_count(self) -> int:
        """Number of requests recorded in the current minute window."""
        now = datetime.now(tz=timezone.utc).timestamp()
        self._prune(now)
        return len(self._minute_window)

    @property
    def current_day_count(self) -> int:
        """Number of requests recorded in the current day window."""
        now = datetime.now(tz=timezone.utc).timestamp()
        self._prune(now)
        return len(self._day_window)

    def reset(self) -> None:
        """Clear all recorded timestamps (useful for tests)."""
        self._minute_window.clear()
        self._day_window.clear()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _prune(self, now: float) -> None:
        """Remove timestamps that have fallen outside the windows."""
        minute_cutoff = now - self._MINUTE_WINDOW
        day_cutoff = now - self._DAY_WINDOW

        while self._minute_window and self._minute_window[0] <= minute_cutoff:
            self._minute_window.popleft()

        while self._day_window and self._day_window[0] <= day_cutoff:
            self._day_window.popleft()

    def _retry_after_minute(self, now: float) -> int:
        """Seconds until the oldest per-minute entry expires."""
        if not self._minute_window:
            return 0
        oldest = self._minute_window[0]
        return max(1, math.ceil(self._MINUTE_WINDOW - (now - oldest)))

    def _retry_after_day(self, now: float) -> int:
        """Seconds until the oldest per-day entry expires."""
        if not self._day_window:
            return 0
        oldest = self._day_window[0]
        return max(1, math.ceil(self._DAY_WINDOW - (now - oldest)))
