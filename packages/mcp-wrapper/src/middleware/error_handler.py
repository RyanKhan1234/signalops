"""Structured error handler for the MCP Wrapper.

All errors surfaced to the Agent Orchestrator conform to the shared SignalOps
error envelope defined in the project overview:

.. code-block:: json

   {
     "error": {
       "code": "string",
       "message": "string",
       "details": {},
       "retry_after_seconds": null
     }
   }

Error codes
-----------
* ``VALIDATION_ERROR`` — bad input parameters (HTTP 400 equivalent)
* ``RATE_LIMIT_EXCEEDED`` — too many requests (HTTP 429 equivalent)
* ``UPSTREAM_ERROR`` — SerpApi returned an error or HTTP failure (HTTP 502)
* ``UPSTREAM_TIMEOUT`` — SerpApi did not respond within the timeout (HTTP 504)
* ``INTERNAL_ERROR`` — unexpected failure (HTTP 500)
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel

from src.middleware.validator import ValidationError as _ValidationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ErrorDetail(BaseModel):
    """Inner error detail block."""

    code: str
    message: str
    details: dict[str, Any] = {}
    retry_after_seconds: int | None = None


class ErrorResponse(BaseModel):
    """Top-level error envelope matching the shared SignalOps error format."""

    error: ErrorDetail


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


def validation_error_response(errors: list[_ValidationError]) -> dict[str, Any]:
    """Build a structured error response for one or more validation failures.

    Parameters
    ----------
    errors:
        List of ``ValidationError`` instances from the validator middleware.

    Returns
    -------
    dict
        Serialised ``ErrorResponse`` ready to return from an MCP tool.
    """
    # Summarise the first error in the top-level message for quick diagnosis.
    first = errors[0]
    details: dict[str, Any] = {
        "validation_errors": [e.model_dump() for e in errors]
    }
    resp = ErrorResponse(
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            message=first.message,
            details=details,
        )
    )
    logger.warning("VALIDATION_ERROR: %s", first.message)
    return resp.model_dump()


def rate_limit_error_response(
    retry_after_seconds: int,
    limit_type: str,
) -> dict[str, Any]:
    """Build a structured error response for rate-limit breaches.

    Parameters
    ----------
    retry_after_seconds:
        How many seconds the caller should wait before retrying.
    limit_type:
        ``"per_minute"`` or ``"per_day"``.

    Returns
    -------
    dict
        Serialised ``ErrorResponse``.
    """
    message = (
        f"Rate limit exceeded ({limit_type.replace('_', ' ')}). "
        f"Retry after {retry_after_seconds} seconds."
    )
    resp = ErrorResponse(
        error=ErrorDetail(
            code="RATE_LIMIT_EXCEEDED",
            message=message,
            details={"limit_type": limit_type},
            retry_after_seconds=retry_after_seconds,
        )
    )
    logger.warning(
        "RATE_LIMIT_EXCEEDED: %s, retry_after=%ds", limit_type, retry_after_seconds
    )
    return resp.model_dump()


def upstream_error_response(
    exc: httpx.HTTPStatusError,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build a structured error response for SerpApi HTTP errors.

    Parameters
    ----------
    exc:
        The ``httpx.HTTPStatusError`` raised by the client.
    request_id:
        Optional request ID for correlation.

    Returns
    -------
    dict
        Serialised ``ErrorResponse``.
    """
    status_code = exc.response.status_code
    message = f"SerpApi returned HTTP {status_code}."
    details: dict[str, Any] = {"http_status": status_code}
    if request_id:
        details["request_id"] = request_id

    resp = ErrorResponse(
        error=ErrorDetail(
            code="UPSTREAM_ERROR",
            message=message,
            details=details,
        )
    )
    logger.error("UPSTREAM_ERROR: SerpApi HTTP %d — %s", status_code, exc)
    return resp.model_dump()


def upstream_timeout_response(
    exc: httpx.TimeoutException,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build a structured error response for SerpApi timeouts.

    Parameters
    ----------
    exc:
        The ``httpx.TimeoutException`` raised by the client.
    request_id:
        Optional request ID for correlation.

    Returns
    -------
    dict
        Serialised ``ErrorResponse``.
    """
    details: dict[str, Any] = {"exception_type": type(exc).__name__}
    if request_id:
        details["request_id"] = request_id

    resp = ErrorResponse(
        error=ErrorDetail(
            code="UPSTREAM_TIMEOUT",
            message="SerpApi did not respond within the allowed timeout.",
            details=details,
        )
    )
    logger.error("UPSTREAM_TIMEOUT: %s", exc)
    return resp.model_dump()


def internal_error_response(
    exc: Exception,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build a structured error response for unexpected internal failures.

    Parameters
    ----------
    exc:
        The unexpected exception.
    request_id:
        Optional request ID for correlation.

    Returns
    -------
    dict
        Serialised ``ErrorResponse``.
    """
    details: dict[str, Any] = {"exception_type": type(exc).__name__}
    if request_id:
        details["request_id"] = request_id

    resp = ErrorResponse(
        error=ErrorDetail(
            code="INTERNAL_ERROR",
            message="An unexpected internal error occurred.",
            details=details,
        )
    )
    logger.exception("INTERNAL_ERROR: %s", exc)
    return resp.model_dump()
