# SignalOps

**Operational Competitive Intelligence Platform**

SignalOps takes natural language prompts from ops teams and returns structured, source-attributed competitive intelligence digests. Every claim is traceable to a source article. There are no hallucinations.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Architecture](#architecture)
4. [Service Reference](#service-reference)
5. [Port Mapping](#port-mapping)
6. [Configuration](#configuration)
7. [Running the Stack](#running-the-stack)
8. [Running Tests](#running-tests)
9. [Development Workflow](#development-workflow)
10. [API Reference](#api-reference)
11. [Contracts](#contracts)
12. [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| Docker Desktop | 24.0+ | Container runtime |
| Docker Compose | 2.20+ (v2 plugin) | Multi-service orchestration |
| Node.js | 18+ | Web app local dev (outside Docker) |
| Python | 3.11+ | E2E tests, local service dev |
| curl | any | Health check scripts |

**API Keys required:**

- `ANTHROPIC_API_KEY` — Claude API key for the Agent Orchestrator
- `SERPAPI_API_KEY` — SerpApi key for the MCP Wrapper (Google News engine)

---

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <repo-url> signalops
cd signalops

# 2. Run the one-command setup
chmod +x scripts/setup.sh
./scripts/setup.sh
```

The setup script will:
- Check prerequisites
- Create `.env` from `.env.example` (and prompt you to fill in API keys)
- Install package dependencies
- Build all Docker images
- Start the full stack
- Run database migrations
- Seed sample data

After setup, open **http://localhost:3000** to use SignalOps.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                          SignalOps Stack                             │
│                                                                      │
│   Browser                                                            │
│      │                                                               │
│      │  HTTP :3000                                                   │
│      ▼                                                               │
│  ┌──────────────────┐                                                │
│  │   web-app        │  React + TypeScript + Vite                     │
│  │   (port 3000)    │  Chat UI, Digest Viewer, Debug Panel           │
│  └────────┬─────────┘                                                │
│           │                                                          │
│           │  POST /digest  (HTTP :8000)                              │
│           │  X-Request-ID propagated →                               │
│           ▼                                                          │
│  ┌──────────────────┐                                                │
│  │ agent-           │  Python + LangChain + LangGraph + FastAPI      │
│  │ orchestrator     │  Intent detection, tool planning,              │
│  │ (port 8000)      │  digest composition, guardrails                │
│  └───┬──────────────┘                                                │
│      │              │                                                │
│      │ MCP/SSE      │ HTTP :8002                                     │
│      │ :8001        │                                                │
│      ▼              ▼                                                │
│  ┌──────────┐  ┌────────────────────┐                               │
│  │ mcp-     │  │ traceability-store │  Python + FastAPI              │
│  │ wrapper  │  │ (port 8002)        │  Audit logs, tool traces,      │
│  │ (port    │  │                    │  source references             │
│  │  8001)   │  └────────┬───────────┘                               │
│  └────┬─────┘           │                                            │
│       │                 │ asyncpg :5432                              │
│       │ HTTPS           ▼                                            │
│       ▼          ┌─────────────┐                                     │
│  ┌──────────┐    │  postgres   │  PostgreSQL 16                      │
│  │  SerpApi │    │  (port 5432)│  reports, tool_calls, sources       │
│  │  (ext.)  │    └─────────────┘                                     │
│  └──────────┘                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **User** types a natural language prompt in the Web App (e.g., "Anything important about Walmart Connect this week?")
2. **Web App** POSTs `{ prompt }` to `agent-orchestrator:8000/digest` with an `X-Request-ID` header
3. **Agent Orchestrator** classifies the intent (weekly_report), extracts entities (Walmart Connect), and plans tool calls
4. **Agent Orchestrator** calls MCP tools on `mcp-wrapper:8001` via SSE transport
5. **MCP Wrapper** validates inputs, checks cache, calls SerpApi, normalizes results, returns article list
6. **Agent Orchestrator** clusters articles, extracts signals, identifies risks/opportunities, generates action items
7. **Agent Orchestrator** logs the full tool trace to `traceability-store:8002`
8. **Agent Orchestrator** returns structured digest JSON to Web App
9. **Web App** renders the digest with executive summary, signals, risks, opportunities, action items, sources, and a collapsible debug panel

---

## Service Reference

| Service | Package | Language | Framework | Role |
|---------|---------|----------|-----------|------|
| `web-app` | `packages/web-app/` | TypeScript | React 18 + Vite | Chat UI and digest viewer |
| `agent-orchestrator` | `packages/agent-orchestrator/` | Python 3.11+ | FastAPI + LangChain | Brain: intent, planning, composition |
| `mcp-wrapper` | `packages/mcp-wrapper/` | Python 3.11+ | MCP SDK | SerpApi gateway with cache and rate limits |
| `traceability-store` | `packages/traceability-store/` | Python 3.11+ | FastAPI + SQLAlchemy | Audit log and query API |
| `postgres` | — | — | PostgreSQL 16 | Persistent storage for traceability data |

---

## Port Mapping

| Service | Container Port | Host Port | Description |
|---------|---------------|-----------|-------------|
| web-app | 3000 | **3000** | React development server |
| agent-orchestrator | 8000 | **8000** | FastAPI — `POST /digest`, `GET /health` |
| mcp-wrapper | 8001 | **8001** | MCP SSE server — `GET /health` |
| traceability-store | 8002 | **8002** | FastAPI — `GET /api/reports`, `GET /health` |
| postgres | 5432 | **5432** | PostgreSQL (for local DB tools) |

---

## Configuration

All configuration is via environment variables. Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

### Required Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key for Agent Orchestrator |
| `SERPAPI_API_KEY` | SerpApi key for MCP Wrapper |

### Database Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `signalops` | PostgreSQL username |
| `POSTGRES_PASSWORD` | `signalops` | PostgreSQL password |
| `POSTGRES_DB` | `signalops` | PostgreSQL database name |
| `DATABASE_URL` | `postgresql+asyncpg://signalops:signalops@postgres:5432/signalops` | SQLAlchemy connection URL |

### Service URLs (Docker internal networking)

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_WRAPPER_URL` | `http://mcp-wrapper:8001` | Agent Orchestrator → MCP Wrapper |
| `TRACEABILITY_STORE_URL` | `http://traceability-store:8002` | Agent Orchestrator → Traceability Store |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Web App → Agent Orchestrator (browser-facing) |

### Optional Tuning Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_TTL_SECONDS` | `900` | News search cache TTL (15 minutes) |
| `RATE_LIMIT_PER_MINUTE` | `30` | Max SerpApi calls per minute |
| `RATE_LIMIT_PER_DAY` | `1000` | Max SerpApi calls per day |
| `LOG_LEVEL` | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## Running the Stack

### Start everything

```bash
docker compose up --build
```

### Start in detached mode (background)

```bash
docker compose up -d --build
```

### View logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f agent-orchestrator
docker compose logs -f mcp-wrapper
```

### Stop everything

```bash
docker compose down
```

### Full reset (removes database volume)

```bash
docker compose down -v
```

### Rebuild a single service

```bash
docker compose build agent-orchestrator
docker compose up -d agent-orchestrator
```

### Run database migrations manually

```bash
docker compose exec traceability-store alembic upgrade head
```

### Seed sample data

```bash
./scripts/seed.sh
```

---

## Running Tests

### End-to-End Tests (Full Stack Required)

E2E tests require the full Docker stack to be running. SerpApi is mocked at the network level using pre-recorded fixtures, so no real API calls are made.

```bash
# Ensure stack is running
docker compose up -d

# Install E2E test dependencies
pip install -r e2e/requirements.txt

# Run all E2E tests
pytest e2e/ -v

# Run a specific scenario
pytest e2e/test_full_pipeline.py::test_happy_path -v
pytest e2e/test_error_scenarios.py::test_rate_limit -v

# Run with coverage report
pytest e2e/ -v --cov=e2e --cov-report=term-missing
```

### Unit Tests (Per Package)

Each package has its own test suite:

```bash
# Agent Orchestrator
docker compose exec agent-orchestrator pytest tests/ -v

# MCP Wrapper
docker compose exec mcp-wrapper pytest tests/ -v

# Traceability Store
docker compose exec traceability-store pytest tests/ -v

# Web App
docker compose exec web-app npm test
```

---

## Development Workflow

### Multi-Agent Development

Each component is developed by a dedicated agent on its own git worktree and branch:

| Component | Branch | Agent |
|-----------|--------|-------|
| Web App | `feat/web-app` | web-app-agent |
| Agent Orchestrator | `feat/agent-orchestrator` | agent-orchestrator-agent |
| MCP Wrapper | `feat/mcp-wrapper` | mcp-wrapper-agent |
| Traceability Store | `feat/traceability-store` | traceability-store-agent |
| Integration | `feat/integration` | integration-agent (this branch) |

### Hot Reload in Development

The `docker-compose.override.yml` file (automatically merged on `docker compose up`) mounts source directories into containers and enables hot reload:

```bash
# Start with dev overrides (automatic)
docker compose up

# Verify override is applied
docker compose config | grep "target: development"
```

### Adding a New Service

1. Create the service package in `packages/<service-name>/`
2. Add a `Dockerfile` with `development` and `production` build targets
3. Add the service to `docker-compose.yml` with proper `depends_on`, `healthcheck`, and `networks`
4. Add development volume mounts to `docker-compose.override.yml`
5. Update `.env.example` with any new environment variables
6. Update this README

---

## API Reference

### Agent Orchestrator

**Base URL:** `http://localhost:8000`

#### `POST /digest`

Submit a natural language prompt and receive a structured competitive intelligence digest.

**Request:**
```http
POST /digest HTTP/1.1
Content-Type: application/json
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000

{
  "prompt": "Anything important about Walmart Connect this week?"
}
```

**Response (200 OK):**
```json
{
  "digest_type": "weekly_report",
  "query": "Anything important about Walmart Connect this week?",
  "generated_at": "2026-03-01T12:00:00Z",
  "report_id": "rpt_abc123",
  "executive_summary": "...",
  "key_signals": [...],
  "risks": [...],
  "opportunities": [...],
  "action_items": [...],
  "sources": [...],
  "tool_trace": [...]
}
```

**Error Response (4xx/5xx):**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "prompt must not be empty",
    "details": { "field": "prompt" },
    "retry_after_seconds": null
  }
}
```

#### `GET /health`

```http
GET /health HTTP/1.1

200 OK
{"status": "healthy"}
```

### Traceability Store

**Base URL:** `http://localhost:8002`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check with DB connectivity |
| `GET` | `/api/reports` | List reports (paginated) |
| `GET` | `/api/reports/{report_id}` | Get full report with digest JSON |
| `GET` | `/api/reports/{report_id}/tool-calls` | Get tool calls for a report |
| `GET` | `/api/reports/{report_id}/sources` | Get sources for a report |
| `GET` | `/api/metrics/tool-latency` | Latency percentiles per tool |
| `GET` | `/api/metrics/error-rate` | Error rates per tool |
| `POST` | `/api/reports` | Create a report (used by Agent Orchestrator) |
| `POST` | `/api/reports/{report_id}/tool-calls` | Log a tool call |
| `POST` | `/api/reports/{report_id}/sources` | Log sources |

---

## Contracts

JSON Schema contracts in `contracts/` are the source of truth for all inter-service communication. If a service's behavior deviates from a contract, it's a bug in the service.

| File | Description |
|------|-------------|
| `contracts/digest-request.json` | Schema for `POST /digest` request body |
| `contracts/digest-response.json` | Schema for digest response (all sections) |
| `contracts/error-response.json` | Schema for all 4xx/5xx error responses |
| `contracts/normalized-article.json` | Schema for MCP Wrapper article responses |

Validate a response against a contract:
```bash
pip install jsonschema
python -c "
import json, jsonschema
schema = json.load(open('contracts/digest-response.json'))
response = json.load(open('my-response.json'))
jsonschema.validate(response, schema)
print('Valid!')
"
```

---

## Troubleshooting

### "Cannot connect to Docker daemon"

Ensure Docker Desktop is running.

### Postgres healthcheck failing

```bash
docker compose logs postgres
# Check for disk space or permission issues
docker compose down -v && docker compose up -d
```

### Agent Orchestrator failing with "MCP Wrapper not reachable"

The MCP Wrapper must be healthy before the orchestrator starts. Check:
```bash
docker compose ps mcp-wrapper
docker compose logs mcp-wrapper
```

### E2E tests failing with "Connection refused"

Ensure the full stack is running before running E2E tests:
```bash
docker compose up -d
docker compose ps  # all services should show "healthy"
pytest e2e/ -v
```

### Database migration errors

```bash
docker compose exec traceability-store alembic history
docker compose exec traceability-store alembic current
docker compose exec traceability-store alembic upgrade head
```

### Reset everything

```bash
docker compose down -v
docker compose up --build -d
./scripts/seed.sh
```

---

## Project Structure

```
signalops/
├── .claude/
│   └── rules/              # Agent rules for each component
├── contracts/
│   ├── digest-request.json
│   ├── digest-response.json
│   ├── error-response.json
│   └── normalized-article.json
├── e2e/
│   ├── conftest.py
│   ├── requirements.txt
│   ├── test_full_pipeline.py
│   ├── test_error_scenarios.py
│   └── fixtures/
├── packages/
│   ├── web-app/            # React + TypeScript frontend
│   ├── agent-orchestrator/ # LangChain orchestration service
│   ├── mcp-wrapper/        # MCP server wrapping SerpApi
│   └── traceability-store/ # PostgreSQL audit log service
├── scripts/
│   ├── init-db.sql         # Postgres initialization
│   ├── setup.sh            # One-command setup
│   └── seed.sh             # Sample data seeding
├── docker-compose.yml
├── docker-compose.override.yml
├── .env.example
├── PRD.md
└── README.md
```
