"""
SignalOps E2E Test Configuration
=================================
Shared fixtures and utilities for all end-to-end tests.

Strategy:
- Tests run against the full Docker Compose stack (agent-orchestrator, mcp-wrapper,
  traceability-store, postgres). The stack must be up before running tests.
- SerpApi is mocked at the httpx transport level inside the mcp-wrapper container.
  Since we cannot inject mocks into the running container directly, E2E tests
  use respx to intercept calls from the TEST PROCESS to the running services,
  and the mcp-wrapper is configured in tests to point to a local mock server
  via SERPAPI_BASE_URL override when running in E2E test mode.
- For true determinism without network access, tests use pre-recorded fixtures
  from e2e/fixtures/ as mock SerpApi responses.

Environment:
  ORCHESTRATOR_URL  - Agent Orchestrator base URL (default: http://localhost:8000)
  TRACEABILITY_URL  - Traceability Store base URL (default: http://localhost:8002)
  MCP_WRAPPER_URL   - MCP Wrapper base URL (default: http://localhost:8001)
  E2E_TIMEOUT       - Global request timeout seconds (default: 60)
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Generator

import httpx
import pytest
import pytest_asyncio

# ─── Configuration ────────────────────────────────────────────────────────────

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")
TRACEABILITY_URL = os.getenv("TRACEABILITY_URL", "http://localhost:8002")
MCP_WRAPPER_URL = os.getenv("MCP_WRAPPER_URL", "http://localhost:8001")
E2E_TIMEOUT = int(os.getenv("E2E_TIMEOUT", "60"))

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CONTRACTS_DIR = Path(__file__).parent.parent / "contracts"


# ─── Pytest configuration ─────────────────────────────────────────────────────

def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (may take > 30s)"
    )
    config.addinivalue_line(
        "markers", "requires_stack: marks tests that require the full Docker stack"
    )


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def orchestrator_url() -> str:
    """Base URL for the Agent Orchestrator service."""
    return ORCHESTRATOR_URL


@pytest.fixture(scope="session")
def traceability_url() -> str:
    """Base URL for the Traceability Store service."""
    return TRACEABILITY_URL


@pytest.fixture(scope="session")
def mcp_wrapper_url() -> str:
    """Base URL for the MCP Wrapper service."""
    return MCP_WRAPPER_URL


@pytest.fixture(scope="session")
def digest_request_schema() -> dict[str, Any]:
    """Load the digest-request JSON Schema contract."""
    schema_path = CONTRACTS_DIR / "digest-request.json"
    return json.loads(schema_path.read_text())


@pytest.fixture(scope="session")
def digest_response_schema() -> dict[str, Any]:
    """Load the digest-response JSON Schema contract."""
    schema_path = CONTRACTS_DIR / "digest-response.json"
    return json.loads(schema_path.read_text())


@pytest.fixture(scope="session")
def error_response_schema() -> dict[str, Any]:
    """Load the error-response JSON Schema contract."""
    schema_path = CONTRACTS_DIR / "error-response.json"
    return json.loads(schema_path.read_text())


@pytest.fixture(scope="session")
def normalized_article_schema() -> dict[str, Any]:
    """Load the normalized-article JSON Schema contract."""
    schema_path = CONTRACTS_DIR / "normalized-article.json"
    return json.loads(schema_path.read_text())


@pytest.fixture(scope="session")
def serpapi_walmart_fixture() -> dict[str, Any]:
    """Pre-recorded SerpApi response for 'Walmart Connect' queries."""
    fixture_path = FIXTURES_DIR / "serpapi_walmart_connect.json"
    return json.loads(fixture_path.read_text())


@pytest.fixture(scope="session")
def serpapi_no_results_fixture() -> dict[str, Any]:
    """Pre-recorded SerpApi response with zero results."""
    fixture_path = FIXTURES_DIR / "serpapi_no_results.json"
    return json.loads(fixture_path.read_text())


@pytest.fixture(scope="session")
def happy_path_digest_fixture() -> dict[str, Any]:
    """Expected digest response structure for happy path test."""
    fixture_path = FIXTURES_DIR / "digest_response_happy_path.json"
    return json.loads(fixture_path.read_text())


@pytest_asyncio.fixture
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client with E2E timeout configured."""
    async with httpx.AsyncClient(timeout=E2E_TIMEOUT) as client:
        yield client


@pytest.fixture
def request_id() -> str:
    """Generate a unique X-Request-ID for each test."""
    return f"e2e-{uuid.uuid4()}"


@pytest.fixture
def base_headers(request_id: str) -> dict[str, str]:
    """Standard headers for all E2E requests."""
    return {
        "Content-Type": "application/json",
        "X-Request-ID": request_id,
    }


# ─── Stack health check ───────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def assert_stack_is_running() -> Generator[None, None, None]:
    """
    Session-scoped fixture that verifies all services are reachable
    before running any tests. Fails fast with a clear error message
    if the stack is not up.
    """
    import httpx as _httpx

    services = {
        "Agent Orchestrator": f"{ORCHESTRATOR_URL}/health",
        "Traceability Store": f"{TRACEABILITY_URL}/health",
        "MCP Wrapper": f"{MCP_WRAPPER_URL}/health",
    }

    unavailable = []
    with _httpx.Client(timeout=5.0) as client:
        for service_name, health_url in services.items():
            try:
                response = client.get(health_url)
                if response.status_code != 200:
                    unavailable.append(
                        f"{service_name} ({health_url}) returned {response.status_code}"
                    )
            except (_httpx.ConnectError, _httpx.TimeoutException):
                unavailable.append(
                    f"{service_name} ({health_url}) — connection refused"
                )

    if unavailable:
        services_list = "\n  - ".join(unavailable)
        pytest.skip(
            f"E2E tests skipped — the following services are not reachable:\n"
            f"  - {services_list}\n\n"
            f"Start the stack with: docker compose up -d\n"
            f"Then re-run: pytest e2e/ -v"
        )

    yield


# ─── Schema validation helper ─────────────────────────────────────────────────

def validate_schema(instance: dict[str, Any], schema: dict[str, Any]) -> None:
    """
    Validate a JSON object against a JSON Schema.
    Raises AssertionError with a descriptive message on failure.
    """
    try:
        import jsonschema
        jsonschema.validate(instance=instance, schema=schema)
    except jsonschema.ValidationError as e:
        raise AssertionError(
            f"Schema validation failed:\n"
            f"  Path: {' -> '.join(str(p) for p in e.absolute_path)}\n"
            f"  Message: {e.message}\n"
            f"  Schema path: {' -> '.join(str(p) for p in e.absolute_schema_path)}"
        ) from e
