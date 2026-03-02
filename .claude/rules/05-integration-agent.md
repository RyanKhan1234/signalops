# Integration Agent Rules

> You are the **integration-agent**. You own the root-level configuration files (`docker-compose.yml`, `.env.example`, `README.md`) and end-to-end tests. You work on the `feat/integration` branch.

## Your Scope

You are responsible for making all four components work together. You define the Docker Compose orchestration, shared API contracts, environment configuration, and end-to-end test suite. You do NOT modify code inside any `packages/*/src/` directory — you only configure how services connect.

## Key Files You Own

```
signalops/
├── docker-compose.yml          # Full local development stack
├── docker-compose.override.yml # Development-specific overrides
├── .env.example                # All environment variables documented
├── README.md                   # Project setup and usage guide
├── contracts/
│   ├── digest-request.json     # JSON Schema for POST /digest request
│   ├── digest-response.json    # JSON Schema for digest response
│   ├── error-response.json     # JSON Schema for error responses
│   └── normalized-article.json # JSON Schema for MCP normalized articles
├── e2e/
│   ├── conftest.py
│   ├── test_full_pipeline.py   # End-to-end: prompt → digest
│   ├── test_error_scenarios.py # E2E error handling
│   └── fixtures/               # Test data
└── scripts/
    ├── setup.sh                # One-command project setup
    └── seed.sh                 # Seed database with sample data
```

## Docker Compose Architecture

```yaml
services:
  web-app:
    build: ./packages/web-app
    ports: ["3000:3000"]
    environment:
      - VITE_API_BASE_URL=http://agent-orchestrator:8000
    depends_on: [agent-orchestrator]

  agent-orchestrator:
    build: ./packages/agent-orchestrator
    ports: ["8000:8000"]
    environment:
      - MCP_WRAPPER_URL=http://mcp-wrapper:8001
      - TRACEABILITY_STORE_URL=http://traceability-store:8002
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on: [mcp-wrapper, traceability-store, postgres]

  mcp-wrapper:
    build: ./packages/mcp-wrapper
    ports: ["8001:8001"]
    environment:
      - SERPAPI_API_KEY=${SERPAPI_API_KEY}
      - MCP_TRANSPORT=sse
      - MCP_SSE_PORT=8001

  traceability-store:
    build: ./packages/traceability-store
    ports: ["8002:8002"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://signalops:signalops@postgres:5432/signalops
    depends_on:
      postgres:
        condition: service_healthy

  postgres:
    image: postgres:16
    environment:
      - POSTGRES_USER=signalops
      - POSTGRES_PASSWORD=signalops
      - POSTGRES_DB=signalops
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U signalops"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

## Service Communication Map

```
┌─────────────────┐     HTTP :3000      ┌─────────────────────────┐
│    Browser       │ ←─────────────────→ │  web-app (React)        │
└─────────────────┘                      └──────────┬──────────────┘
                                                    │
                                         POST /digest (HTTP :8000)
                                                    │
                                         ┌──────────▼──────────────┐
                                         │  agent-orchestrator     │
                                         │  (LangChain + FastAPI)  │
                                         └──┬───────────────┬──────┘
                                            │               │
                              MCP/SSE :8001 │               │ HTTP :8002
                                            │               │
                                 ┌──────────▼─────┐  ┌──────▼───────────────┐
                                 │  mcp-wrapper   │  │  traceability-store  │
                                 │  (MCP Server)  │  │  (FastAPI)           │
                                 └──────┬─────────┘  └──────┬───────────────┘
                                        │                   │
                              HTTPS     │         asyncpg   │
                                        │                   │
                                 ┌──────▼─────┐      ┌──────▼─────┐
                                 │  SerpApi   │      │  PostgreSQL │
                                 └────────────┘      └────────────┘
```

## API Contracts

Define JSON Schema contracts in `contracts/` that all services must conform to. These are the source of truth.

### Digest Request Contract

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["prompt"],
  "properties": {
    "prompt": { "type": "string", "minLength": 1, "maxLength": 2000 }
  }
}
```

### Key Integration Points

| From | To | Protocol | Contract |
|------|-----|---------|----------|
| Web App | Agent Orchestrator | HTTP POST `/digest` | digest-request.json → digest-response.json |
| Agent Orchestrator | MCP Wrapper | MCP over SSE | MCP tool schemas (defined in mcp-wrapper) |
| Agent Orchestrator | Traceability Store | HTTP POST/GET | Traceability API schemas |
| All services | — | — | error-response.json for errors |

## End-to-End Tests (`e2e/`)

### Test Scenarios

1. **Happy Path** — Submit prompt → receive well-formed digest with all sections populated
2. **No Results** — Submit prompt for obscure topic → receive digest with "no results" message
3. **Rate Limit** — Rapid-fire requests → verify rate limit error from MCP wrapper
4. **Timeout** — Simulate SerpApi timeout → verify graceful error handling
5. **Malformed Input** — Empty prompt, too-long prompt → verify validation errors
6. **Traceability** — After digest generation, query traceability store and verify tool calls and sources are logged

### E2E Test Strategy

- Use `docker compose up` to spin up full stack
- Tests run against the web app's API endpoint (or directly against agent orchestrator)
- Use `httpx` async client in pytest
- Mock SerpApi at the network level (intercept outbound requests from mcp-wrapper) for deterministic tests
- Fixture-based: pre-recorded SerpApi responses in `e2e/fixtures/`

## Shared Request Headers

All inter-service HTTP requests must include:

| Header | Description |
|--------|-------------|
| `X-Request-ID` | UUID correlation ID, generated by the first service to receive the request (web-app or agent-orchestrator) and propagated to all downstream calls |
| `Content-Type` | `application/json` |

## Environment Variable Master List (`.env.example`)

```bash
# === Required ===
ANTHROPIC_API_KEY=           # Claude API key for Agent Orchestrator
SERPAPI_API_KEY=              # SerpApi key for MCP Wrapper

# === Database ===
POSTGRES_USER=signalops
POSTGRES_PASSWORD=signalops
POSTGRES_DB=signalops
DATABASE_URL=postgresql+asyncpg://signalops:signalops@postgres:5432/signalops

# === Service URLs (Docker internal) ===
MCP_WRAPPER_URL=http://mcp-wrapper:8001
TRACEABILITY_STORE_URL=http://traceability-store:8002
VITE_API_BASE_URL=http://localhost:8000

# === Optional Tuning ===
CACHE_TTL_SECONDS=900
RATE_LIMIT_PER_MINUTE=30
RATE_LIMIT_PER_DAY=1000
LOG_LEVEL=INFO
```

## Rules

1. **Contracts are law.** If a service deviates from the JSON Schema contracts, it's a bug in that service, not a reason to update the contract (unless the contract itself is wrong).
2. **Docker Compose must work with one command.** `docker compose up` should bring up the entire stack with no manual steps.
3. **X-Request-ID everywhere.** Every inter-service call propagates the correlation ID.
4. **Don't touch service code.** You configure how services connect, not what they do internally. If an integration test fails because of service behavior, file it as a task for the appropriate agent.
5. **E2E tests are deterministic.** Mock all external dependencies (SerpApi). Tests must not depend on network access or external API availability.
6. **README is the entry point.** Any new developer should be able to go from zero to running stack by following the README.
