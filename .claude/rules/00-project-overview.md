# SignalOps — Shared Project Context

> This file is read by ALL Claude Code agents working on SignalOps. It provides the shared understanding that every agent must internalize before doing any work.

## What Is SignalOps?

SignalOps is an operational competitive intelligence platform. It takes natural language prompts from ops teams (RevOps, Marketing Ops, Product Ops, Strategy) and returns structured, source-attributed competitive intelligence digests. Every claim is traceable to a source article. There are no hallucinations.

## Architecture at a Glance

```
Ops Team → Web App (React/TS) → Agent Orchestrator (LangChain/Python) → Traceability Store (PostgreSQL)
                                         ↕
                                  MCP Wrapper (Python) → SerpApi
```

## Four Components, Four Agents

| Component | Package Path | Language | Agent Branch |
|-----------|-------------|----------|-------------|
| Web App | `packages/web-app/` | TypeScript (React) | `feat/web-app` |
| Agent Orchestrator | `packages/agent-orchestrator/` | Python | `feat/agent-orchestrator` |
| MCP Wrapper | `packages/mcp-wrapper/` | Python | `feat/mcp-wrapper` |
| Traceability Store | `packages/traceability-store/` | Python | `feat/traceability-store` |

A fifth **integration-agent** owns `docker-compose.yml`, API contracts, and E2E tests.

## Core Data Flow

1. User sends natural language prompt via Web App
2. Web App POSTs to `/digest` endpoint on Agent Orchestrator
3. Agent Orchestrator detects intent (daily_digest | weekly_report | risk_alert | competitor_monitor)
4. Agent Orchestrator calls MCP tools (`search_news`, `search_company_news`, etc.)
5. MCP Wrapper validates, caches, rate-limits, and forwards to SerpApi
6. MCP Wrapper returns normalized article JSON
7. Agent clusters articles, extracts signals, identifies risks/opportunities, generates action items
8. Agent composes structured digest and logs tool trace to Traceability Store
9. Structured digest JSON returned to Web App for rendering

## Shared Conventions

### API Communication
- All inter-service communication uses JSON over HTTP
- Request correlation IDs (`X-Request-ID` header) propagated through entire pipeline
- All timestamps in ISO 8601 UTC

### Error Format
```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {},
    "retry_after_seconds": null
  }
}
```

### Environment Variables
- All secrets via environment variables (never hardcoded)
- `.env.example` at repo root documents all required vars
- Each package has its own `.env.example` for package-specific config

### Git Workflow
- Each agent works on its own `feat/*` branch in a dedicated git worktree
- RALPH loop: Read → Act → Log → Push → Halt
- Agents must not modify files outside their designated `packages/` directory
- Integration agent handles cross-cutting concerns
- PRs require passing CI checks before merge

### Testing
- Python: pytest with `pytest-asyncio` for async code
- TypeScript: Vitest
- Minimum 80% coverage for business logic
- E2E tests owned by integration agent

### Code Style
- Python: Ruff for linting and formatting, type hints required on all public functions
- TypeScript: ESLint + Prettier, strict mode enabled
- Docstrings/JSDoc on all public interfaces

## The Guardrail Principle

**Every statement in a digest must be traceable to a source article.** If the agent cannot find supporting sources, it must say "No relevant articles found for this query" rather than fabricate intelligence. This is the most critical invariant in the system.
