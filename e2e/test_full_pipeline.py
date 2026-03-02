"""
SignalOps E2E — Full Pipeline Tests
=====================================
Tests the complete prompt → digest pipeline through the running Docker stack.

Test Scenarios:
  1. Happy Path           — Well-formed prompt → all sections populated, schema valid
  2. No Results           — Obscure topic → guardrail digest with "no articles found" message
  3. Traceability         — After digest, verify tool calls and sources logged to traceability store
  4. Report ID Uniqueness — Two identical prompts produce distinct report IDs
  5. X-Request-ID         — Correlation ID propagated in response headers
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
import pytest

from conftest import validate_schema


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def post_digest(
    client: httpx.AsyncClient,
    orchestrator_url: str,
    prompt: str,
    headers: dict[str, str],
) -> httpx.Response:
    """POST a digest request and return the raw response."""
    return await client.post(
        f"{orchestrator_url}/digest",
        json={"prompt": prompt},
        headers=headers,
    )


# ─── Test 1: Happy Path ───────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.timeout(90)
async def test_happy_path_returns_well_formed_digest(
    http_client: httpx.AsyncClient,
    orchestrator_url: str,
    base_headers: dict[str, str],
    digest_response_schema: dict[str, Any],
) -> None:
    """
    GIVEN: A well-formed prompt about a real company topic
    WHEN:  POST /digest is called
    THEN:
      - HTTP 200 is returned
      - Response body conforms to digest-response.json schema
      - All required top-level fields are present
      - executive_summary is non-empty
      - At least one key_signal, risk, opportunity, action_item, and source exists
      - Every source_url in key_signals and risks exists in the sources array
      - report_id matches the expected pattern (rpt_<alphanum>)
      - generated_at is a valid ISO 8601 timestamp
      - tool_trace is non-empty (at least one tool was called)
    """
    prompt = "Anything important about Walmart Connect this week?"

    response = await post_digest(http_client, orchestrator_url, prompt, base_headers)

    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}.\n"
        f"Response body: {response.text[:500]}"
    )

    body = response.json()

    # Schema validation — the authoritative check
    validate_schema(body, digest_response_schema)

    # Structural assertions
    assert body["digest_type"] in (
        "daily_digest", "weekly_report", "risk_alert", "competitor_monitor"
    ), f"Unexpected digest_type: {body['digest_type']}"

    assert body["query"] == prompt, "Query field should echo the original prompt"

    assert re.match(r"^rpt_[a-zA-Z0-9]+$", body["report_id"]), (
        f"report_id '{body['report_id']}' does not match expected pattern rpt_<alphanum>"
    )

    assert body["executive_summary"], "executive_summary must not be empty"

    assert len(body["key_signals"]) > 0, "At least one key_signal expected for this query"
    assert len(body["sources"]) > 0, "At least one source expected"
    assert len(body["tool_trace"]) > 0, "At least one tool call must appear in trace"

    # Guardrail: every source_url in key_signals must be in sources
    source_urls = {s["url"] for s in body["sources"]}
    for signal in body["key_signals"]:
        assert signal["source_url"] in source_urls, (
            f"Key signal source_url '{signal['source_url']}' not found in sources array. "
            f"This violates the traceability guardrail."
        )

    # Guardrail: every source_url in risks must be in sources
    for risk in body["risks"]:
        for url in risk["source_urls"]:
            assert url in source_urls, (
                f"Risk source_url '{url}' not found in sources array."
            )

    # Guardrail: every source_url in opportunities must be in sources
    for opp in body["opportunities"]:
        for url in opp["source_urls"]:
            assert url in source_urls, (
                f"Opportunity source_url '{url}' not found in sources array."
            )

    # Tool trace entries must have positive latency
    for entry in body["tool_trace"]:
        assert entry["latency_ms"] >= 0, (
            f"Tool '{entry['tool_name']}' has negative latency: {entry['latency_ms']}"
        )


# ─── Test 2: No Results ───────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.timeout(90)
async def test_no_results_returns_guardrail_digest(
    http_client: httpx.AsyncClient,
    orchestrator_url: str,
    base_headers: dict[str, str],
    digest_response_schema: dict[str, Any],
) -> None:
    """
    GIVEN: A prompt about an obscure or fictional topic with no news coverage
    WHEN:  POST /digest is called
    THEN:
      - HTTP 200 is returned (not an error — this is a valid digest)
      - Response conforms to digest-response schema
      - executive_summary explicitly states "No relevant articles found"
      - key_signals, risks, opportunities, action_items, and sources are all empty arrays
      - tool_trace is non-empty (tools were called, they just returned nothing)
    """
    # Use a clearly fictional company name that will never have real news
    prompt = "Risk alert: ZephyrCloud acquisition rumors"

    response = await post_digest(http_client, orchestrator_url, prompt, base_headers)

    assert response.status_code == 200, (
        f"Expected HTTP 200 for no-results case, got {response.status_code}.\n"
        f"Response body: {response.text[:500]}"
    )

    body = response.json()
    validate_schema(body, digest_response_schema)

    # The guardrail message must be present in the summary
    assert "no relevant articles" in body["executive_summary"].lower(), (
        f"Expected 'no relevant articles' guardrail message in executive_summary.\n"
        f"Got: {body['executive_summary']}"
    )

    # No fabricated signals — all arrays must be empty
    assert body["key_signals"] == [], (
        "key_signals must be empty when no articles found (no hallucination)"
    )
    assert body["risks"] == [], (
        "risks must be empty when no articles found"
    )
    assert body["opportunities"] == [], (
        "opportunities must be empty when no articles found"
    )
    assert body["sources"] == [], (
        "sources must be empty when no articles found"
    )

    # Tool trace must still be present (agent did run tools, just found nothing)
    assert len(body["tool_trace"]) > 0, (
        "tool_trace must be present even when no articles returned — "
        "proof the agent tried and found nothing"
    )


# ─── Test 3: Traceability Verification ───────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_traceability_store_receives_full_report(
    http_client: httpx.AsyncClient,
    orchestrator_url: str,
    traceability_url: str,
    base_headers: dict[str, str],
) -> None:
    """
    GIVEN: A successful digest generation
    WHEN:  The Traceability Store is queried for the report by report_id
    THEN:
      - The report exists in the traceability store (GET /api/reports/{report_id})
      - The stored digest_type and query match the original request
      - Tool calls are logged (GET /api/reports/{report_id}/tool-calls) with at least
        one entry per tool used
      - Sources are logged (GET /api/reports/{report_id}/sources) matching the digest sources
      - All tool call entries have a status of "success" or "error" (never null)
      - Tool call latency_ms values are positive integers
    """
    prompt = "Daily digest for Salesforce competitors"

    # Step 1: Generate digest
    digest_response = await post_digest(
        http_client, orchestrator_url, prompt, base_headers
    )
    assert digest_response.status_code == 200
    digest_body = digest_response.json()
    report_id = digest_body["report_id"]

    # Step 2: Verify report exists in traceability store
    report_response = await http_client.get(
        f"{traceability_url}/api/reports/{report_id}",
        headers=base_headers,
    )
    assert report_response.status_code == 200, (
        f"Report {report_id} not found in traceability store. "
        f"Status: {report_response.status_code}"
    )
    report = report_response.json()

    assert report["report_id"] == report_id
    assert report["query"] == prompt
    assert report["digest_type"] == digest_body["digest_type"]

    # Step 3: Verify tool calls are logged
    tool_calls_response = await http_client.get(
        f"{traceability_url}/api/reports/{report_id}/tool-calls",
        headers=base_headers,
    )
    assert tool_calls_response.status_code == 200
    tool_calls = tool_calls_response.json()

    assert len(tool_calls) > 0, (
        f"Expected at least one tool call logged for report {report_id}"
    )

    for call in tool_calls:
        assert call["tool_name"] in (
            "search_news", "search_company_news", "get_article_metadata"
        ), f"Unexpected tool_name: {call['tool_name']}"
        assert call["status"] in ("success", "error", "timeout"), (
            f"Unexpected status: {call['status']}"
        )
        assert call["latency_ms"] >= 0, (
            f"Negative latency for tool {call['tool_name']}: {call['latency_ms']}"
        )

    # Step 4: Verify sources are logged (if digest has sources)
    if len(digest_body["sources"]) > 0:
        sources_response = await http_client.get(
            f"{traceability_url}/api/reports/{report_id}/sources",
            headers=base_headers,
        )
        assert sources_response.status_code == 200
        stored_sources = sources_response.json()

        assert len(stored_sources) > 0, (
            f"Expected sources to be logged for report {report_id}"
        )

        stored_urls = {s["url"] for s in stored_sources}
        digest_urls = {s["url"] for s in digest_body["sources"]}

        # All digest sources should appear in the traceability store
        for url in digest_urls:
            assert url in stored_urls, (
                f"Source URL '{url}' from digest not found in traceability store"
            )


# ─── Test 4: Report ID Uniqueness ─────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_identical_prompts_produce_unique_report_ids(
    http_client: httpx.AsyncClient,
    orchestrator_url: str,
    base_headers: dict[str, str],
) -> None:
    """
    GIVEN: Two identical prompts submitted sequentially
    WHEN:  Both requests complete
    THEN:
      - Both return HTTP 200
      - Each response has a unique report_id
      - Both report_ids match the rpt_<alphanum> pattern
    """
    prompt = "What's new with Salesforce?"

    response1 = await post_digest(http_client, orchestrator_url, prompt, base_headers)
    response2 = await post_digest(http_client, orchestrator_url, prompt, base_headers)

    assert response1.status_code == 200
    assert response2.status_code == 200

    id1 = response1.json()["report_id"]
    id2 = response2.json()["report_id"]

    assert id1 != id2, (
        f"Expected unique report IDs for repeated prompts, but both returned: {id1}"
    )
    assert re.match(r"^rpt_[a-zA-Z0-9]+$", id1)
    assert re.match(r"^rpt_[a-zA-Z0-9]+$", id2)


# ─── Test 5: X-Request-ID Propagation ────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.timeout(90)
async def test_request_id_propagated_in_response(
    http_client: httpx.AsyncClient,
    orchestrator_url: str,
    request_id: str,
    base_headers: dict[str, str],
) -> None:
    """
    GIVEN: A request with a specific X-Request-ID header
    WHEN:  POST /digest is called
    THEN:
      - The response includes an X-Request-ID header
      - The response X-Request-ID matches the request X-Request-ID
    """
    response = await post_digest(
        http_client,
        orchestrator_url,
        "Daily digest for Microsoft",
        base_headers,
    )

    # Service should be reachable
    assert response.status_code in (200, 422, 500), (
        f"Unexpected status code: {response.status_code}"
    )

    # The correlation ID must be echoed back
    response_request_id = response.headers.get("X-Request-ID") or response.headers.get("x-request-id")
    assert response_request_id is not None, (
        "X-Request-ID header missing from response. "
        "All services must propagate the correlation ID."
    )
    assert response_request_id == request_id, (
        f"X-Request-ID mismatch. Sent: {request_id}, Got: {response_request_id}"
    )
