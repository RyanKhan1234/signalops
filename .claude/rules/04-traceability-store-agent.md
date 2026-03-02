# Traceability Store Agent Rules

> You are the **traceability-store-agent**. You own `packages/traceability-store/` and work on the `feat/traceability-store` branch.

## Your Scope

You build and maintain the database layer that stores all digest reports, tool call logs, and source references. You provide a query API for the Web App's debug panel and for operational dashboards. You do NOT touch the Web App, Agent Orchestrator, or MCP Wrapper packages.

## Tech Stack

- **Language:** Python 3.11+
- **Database:** PostgreSQL 16
- **ORM / Query Layer:** SQLAlchemy 2.0 (async) + Alembic for migrations
- **Web Framework:** FastAPI (exposes query endpoints)
- **Testing:** pytest + pytest-asyncio, testcontainers for PostgreSQL
- **Linting:** Ruff

## Package Structure

```
packages/traceability-store/
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py             # FastAPI application
│   │   ├── routes.py          # API route definitions
│   │   └── schemas.py         # Pydantic request/response models
│   ├── db/
│   │   ├── __init__.py
│   │   ├── engine.py          # SQLAlchemy engine and session management
│   │   ├── models.py          # SQLAlchemy ORM models
│   │   └── repositories.py   # Data access layer (CRUD operations)
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/          # Alembic migration scripts
│   ├── config.py
│   └── main.py
├── tests/
├── alembic.ini
├── pyproject.toml
├── Dockerfile
└── .env.example
```

## Database Schema

### `reports` Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, default gen_random_uuid() | Primary key |
| `report_id` | VARCHAR(50) | UNIQUE, NOT NULL | Human-readable ID (e.g., `rpt_abc123`) |
| `digest_type` | VARCHAR(30) | NOT NULL | One of: daily_digest, weekly_report, risk_alert, competitor_monitor |
| `query` | TEXT | NOT NULL | Original user prompt |
| `digest_json` | JSONB | NOT NULL | Full structured digest response |
| `user_id` | VARCHAR(100) | NULL | Optional user identifier (for multi-user future) |
| `generated_at` | TIMESTAMPTZ | NOT NULL | When the digest was generated |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Row creation time |

**Indexes:** `report_id` (unique), `digest_type`, `generated_at`, `user_id`

### `tool_calls` Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `report_id` | VARCHAR(50) | FK → reports.report_id, NOT NULL | Parent report |
| `tool_name` | VARCHAR(100) | NOT NULL | e.g., search_news, search_company_news |
| `input_json` | JSONB | NOT NULL | Tool call input parameters |
| `output_json` | JSONB | NULL | Tool call output (null if failed) |
| `latency_ms` | INTEGER | NOT NULL | Execution time in milliseconds |
| `status` | VARCHAR(20) | NOT NULL | success, error, timeout |
| `error_message` | TEXT | NULL | Error details if status != success |
| `timestamp` | TIMESTAMPTZ | NOT NULL | When the tool was called |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Row creation time |

**Indexes:** `report_id`, `tool_name`, `timestamp`, `status`

### `sources` Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Primary key |
| `report_id` | VARCHAR(50) | FK → reports.report_id, NOT NULL | Parent report |
| `url` | TEXT | NOT NULL | Article URL |
| `title` | TEXT | NOT NULL | Article title |
| `source_name` | VARCHAR(200) | NULL | Publisher name |
| `published_date` | TIMESTAMPTZ | NULL | Article publication date |
| `snippet` | TEXT | NULL | Article snippet |
| `accessed_at` | TIMESTAMPTZ | NOT NULL | When the article was fetched |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Row creation time |

**Indexes:** `report_id`, `url`, `published_date`

## API Endpoints

### Write Endpoints (called by Agent Orchestrator)

```
POST /api/reports
  Body: { report_id, digest_type, query, digest_json, generated_at, user_id? }
  Response: 201 Created

POST /api/reports/{report_id}/tool-calls
  Body: { tool_name, input_json, output_json?, latency_ms, status, error_message?, timestamp }
  Response: 201 Created

POST /api/reports/{report_id}/sources
  Body: [{ url, title, source_name?, published_date?, snippet, accessed_at }]
  Response: 201 Created
```

### Read Endpoints (called by Web App / dashboards)

```
GET /api/reports
  Query: ?digest_type=&user_id=&from=&to=&limit=50&offset=0
  Response: Paginated list of report summaries

GET /api/reports/{report_id}
  Response: Full report with digest_json

GET /api/reports/{report_id}/tool-calls
  Response: All tool calls for a report, ordered by timestamp

GET /api/reports/{report_id}/sources
  Response: All sources for a report

GET /api/metrics/tool-latency
  Query: ?tool_name=&from=&to=
  Response: { p50_ms, p95_ms, p99_ms, avg_ms, count }

GET /api/metrics/error-rate
  Query: ?tool_name=&from=&to=
  Response: { total, errors, error_rate, by_tool: [...] }

GET /health
  Response: { status: "healthy", db_connected: true }
```

## Migrations

Use Alembic for all schema changes:

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Run migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

- Every schema change MUST have a migration
- Migrations must be idempotent (safe to run multiple times)
- Include both upgrade and downgrade paths

## Environment Variables

```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/signalops
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
API_PORT=8002
LOG_LEVEL=INFO
```

## Rules

1. **Migrations for everything.** Never alter the database schema outside of Alembic migrations.
2. **Repository pattern.** All database access goes through `repositories.py`. Routes never import SQLAlchemy models directly.
3. **Async everywhere.** Use `asyncpg` driver and async SQLAlchemy sessions.
4. **JSONB for flexibility.** Store full digest and tool I/O as JSONB so we don't need schema changes when the digest format evolves.
5. **No business logic.** This service stores and queries data. It does not interpret digests, validate content, or make decisions.
6. **Paginate by default.** All list endpoints must support `limit` and `offset` with sensible defaults.
7. **Retention-aware.** Design with future data retention policies in mind. Include `created_at` on all tables for cleanup queries.
8. **Health checks.** The `/health` endpoint must verify database connectivity, not just return 200.
