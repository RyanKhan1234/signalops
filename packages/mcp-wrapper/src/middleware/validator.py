"""Input validation middleware for MCP tool calls.

All tool inputs are validated *before* any SerpApi request is made.  Invalid
inputs are rejected immediately with a structured ``ValidationError`` response
so that we never send garbage to the upstream API.

Validation rules
----------------
* ``query`` / ``company``: non-empty string, max 200 characters, no injection
  characters (``<>``, ``{}``, null bytes).
* ``time_range``: one of ``"1d"``, ``"7d"``, ``"30d"``, ``"1y"``.
* ``num_results``: integer between 1 and 50 (inclusive).
* ``topics``: if provided, a list of strings each at most 100 characters, no
  injection characters.
* ``url``: must be a valid ``http`` or ``https`` URL.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_TIME_RANGES: frozenset[str] = frozenset({"1d", "7d", "30d", "1y"})
MAX_QUERY_LENGTH: int = 200
MAX_TOPIC_LENGTH: int = 100
MIN_NUM_RESULTS: int = 1
MAX_NUM_RESULTS: int = 50

# Characters that are never valid in a search query — guard against injection.
_INJECTION_PATTERN = re.compile(r"[<>{}\x00]")


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------


class ValidationError(BaseModel):
    """Structured validation error returned when tool inputs are invalid."""

    code: str = "VALIDATION_ERROR"
    message: str
    field: str
    constraint: str


# ---------------------------------------------------------------------------
# Public validation functions
# ---------------------------------------------------------------------------


def validate_query(query: str | None) -> ValidationError | None:
    """Validate the ``query`` parameter for ``search_news``.

    Returns
    -------
    ValidationError | None
        A ``ValidationError`` if validation fails, ``None`` if the input is valid.
    """
    if not query or not query.strip():
        return ValidationError(
            message="The 'query' field must not be empty.",
            field="query",
            constraint="non_empty",
        )
    if len(query) > MAX_QUERY_LENGTH:
        return ValidationError(
            message=(
                f"The 'query' field must be at most {MAX_QUERY_LENGTH} characters; "
                f"got {len(query)}."
            ),
            field="query",
            constraint=f"max_length:{MAX_QUERY_LENGTH}",
        )
    if _INJECTION_PATTERN.search(query):
        return ValidationError(
            message="The 'query' field contains disallowed characters.",
            field="query",
            constraint="no_injection_chars",
        )
    return None


def validate_company(company: str | None) -> ValidationError | None:
    """Validate the ``company`` parameter for ``search_company_news``."""
    if not company or not company.strip():
        return ValidationError(
            message="The 'company' field must not be empty.",
            field="company",
            constraint="non_empty",
        )
    if len(company) > MAX_QUERY_LENGTH:
        return ValidationError(
            message=(
                f"The 'company' field must be at most {MAX_QUERY_LENGTH} characters; "
                f"got {len(company)}."
            ),
            field="company",
            constraint=f"max_length:{MAX_QUERY_LENGTH}",
        )
    if _INJECTION_PATTERN.search(company):
        return ValidationError(
            message="The 'company' field contains disallowed characters.",
            field="company",
            constraint="no_injection_chars",
        )
    return None


def validate_time_range(time_range: str | None) -> ValidationError | None:
    """Validate the ``time_range`` parameter."""
    if time_range is None:
        return None  # Optional; caller uses default.
    if time_range not in VALID_TIME_RANGES:
        valid = sorted(VALID_TIME_RANGES)
        return ValidationError(
            message=(
                f"The 'time_range' field must be one of {valid}; got {time_range!r}."
            ),
            field="time_range",
            constraint=f"one_of:{','.join(valid)}",
        )
    return None


def validate_num_results(num_results: int | None) -> ValidationError | None:
    """Validate the ``num_results`` parameter."""
    if num_results is None:
        return None  # Optional; caller uses default.
    if not isinstance(num_results, int) or isinstance(num_results, bool):
        return ValidationError(
            message="The 'num_results' field must be an integer.",
            field="num_results",
            constraint="type:integer",
        )
    if num_results < MIN_NUM_RESULTS or num_results > MAX_NUM_RESULTS:
        return ValidationError(
            message=(
                f"The 'num_results' field must be between {MIN_NUM_RESULTS} and "
                f"{MAX_NUM_RESULTS}; got {num_results}."
            ),
            field="num_results",
            constraint=f"range:{MIN_NUM_RESULTS}-{MAX_NUM_RESULTS}",
        )
    return None


def validate_topics(topics: list[str] | None) -> ValidationError | None:
    """Validate the ``topics`` parameter for ``search_company_news``."""
    if topics is None:
        return None  # Optional.
    if not isinstance(topics, list):
        return ValidationError(
            message="The 'topics' field must be a list of strings.",
            field="topics",
            constraint="type:list[str]",
        )
    for i, topic in enumerate(topics):
        if not isinstance(topic, str) or not topic.strip():
            return ValidationError(
                message=f"topics[{i}] must be a non-empty string.",
                field=f"topics[{i}]",
                constraint="non_empty_string",
            )
        if len(topic) > MAX_TOPIC_LENGTH:
            return ValidationError(
                message=(
                    f"topics[{i}] must be at most {MAX_TOPIC_LENGTH} characters; "
                    f"got {len(topic)}."
                ),
                field=f"topics[{i}]",
                constraint=f"max_length:{MAX_TOPIC_LENGTH}",
            )
        if _INJECTION_PATTERN.search(topic):
            return ValidationError(
                message=f"topics[{i}] contains disallowed characters.",
                field=f"topics[{i}]",
                constraint="no_injection_chars",
            )
    return None


def validate_url(url: str | None) -> ValidationError | None:
    """Validate the ``url`` parameter for ``get_article_metadata``."""
    if not url or not url.strip():
        return ValidationError(
            message="The 'url' field must not be empty.",
            field="url",
            constraint="non_empty",
        )
    try:
        parsed = urlparse(url)
    except Exception:
        return ValidationError(
            message="The 'url' field is not a valid URL.",
            field="url",
            constraint="valid_url",
        )
    if parsed.scheme not in {"http", "https"}:
        return ValidationError(
            message="The 'url' field must use the http or https scheme.",
            field="url",
            constraint="scheme:http_or_https",
        )
    if not parsed.netloc:
        return ValidationError(
            message="The 'url' field must include a valid host.",
            field="url",
            constraint="valid_host",
        )
    return None


# ---------------------------------------------------------------------------
# Composite validators (one call per tool)
# ---------------------------------------------------------------------------


def validate_search_news_inputs(
    query: str | None,
    time_range: str | None = None,
    num_results: int | None = None,
) -> list[ValidationError]:
    """Validate all inputs for the ``search_news`` tool.

    Returns
    -------
    list[ValidationError]
        All validation errors found; empty list means all inputs are valid.
    """
    errors: list[ValidationError] = []
    for check in (
        validate_query(query),
        validate_time_range(time_range),
        validate_num_results(num_results),
    ):
        if check is not None:
            errors.append(check)
    return errors


def validate_search_company_news_inputs(
    company: str | None,
    time_range: str | None = None,
    topics: list[str] | None = None,
) -> list[ValidationError]:
    """Validate all inputs for the ``search_company_news`` tool."""
    errors: list[ValidationError] = []
    for check in (
        validate_company(company),
        validate_time_range(time_range),
        validate_topics(topics),
    ):
        if check is not None:
            errors.append(check)
    return errors


def validate_get_article_metadata_inputs(
    url: str | None,
) -> list[ValidationError]:
    """Validate all inputs for the ``get_article_metadata`` tool."""
    errors: list[ValidationError] = []
    check = validate_url(url)
    if check is not None:
        errors.append(check)
    return errors
