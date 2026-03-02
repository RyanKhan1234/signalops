# SignalOps — Product Requirements Document

## Operational Competitive Intelligence Analyst

**Version:** 1.0
**Date:** March 2026
**Status:** Draft

---

## 1. Overview

### 1.1 Vision

SignalOps automates structured competitive intelligence digests for operations teams with full traceability and standardized outputs. It replaces ad-hoc manual research with an AI-powered agent pipeline that detects intent from natural language prompts, orchestrates tool calls against public news APIs, and returns structured, auditable digests.

### 1.2 Primary Users

- **RevOps** — Revenue operations teams tracking competitor pricing, partnerships, and GTM moves
- **Marketing Ops** — Teams monitoring competitor messaging, campaigns, and positioning shifts
- **Product Ops** — Teams tracking competitor feature launches, roadmap signals, and platform changes
- **Strategy** — Leadership teams needing synthesized competitive landscape views

### 1.3 Core Use Cases

- **Daily Digest** — Quick morning brief on overnight competitor activity
- **Weekly Report** — Comprehensive weekly competitive intelligence rollup
- **Risk Alert** — Real-time detection of competitor moves that threaten current strategy
- **New Competitor Monitor** — Emerging player detection in adjacent spaces

---

## 2. System Architecture

The system consists of four primary components connected in a request/response pipeline:

```
Ops Team → Web App (React) → Agent Orchestrator (LangChain) → Traceability Store
                                       ↓
                               MCP Wrapper → SerpApi (Public News API)
```

### 2.1 Component Summary

| Component | Technology | Responsibility |
|-----------|-----------|----------------|
| Web App | React (TypeScript) | Chat UI, digest viewer, debug panel, tool call + source display |
| Agent Orchestrator | LangChain (Python) | Intent detection, tool selection/sequencing, digest composition, guardrails, audit logging |
| MCP Wrapper | Python (MCP SDK) | API key management, input validation, response normalization, caching, rate limiting, error formatting |
| Traceability Store | PostgreSQL + optional vector store | Tool call logs, latency metrics, report IDs, source references |
| Public News API | SerpApi | Article search, metadata extraction, URL retrieval |

---

## 3. Component Specifications

### 3.1 Web App (React)

**Route:** `/chat` — primary interaction surface

**Core Features:**

- **Chat Input** — Natural language prompt interface where ops team members submit requests (e.g., "Anything important about Walmart Connect this week?")
- **Digest Viewer** — Renders structured digest responses with sections for executive summary, key signals, risks, opportunities, action items, and sources
- **Debug Panel** — Expandable panel showing tool calls made, latency per call, sources accessed, and the full agent reasoning trace
- **Tool Calls & Sources** — Inline display of which tools were invoked, what data was retrieved, and links to original source articles

**API Contract:**

- `POST /digest` — Sends chat request payload to the Agent Orchestrator
- Receives a structured digest JSON response
- Supports streaming for long-running digests (SSE)

**UI Sections for Digest Display:**

1. Executive Summary
2. Key Signals
3. Risks
4. Opportunities
5. Action Items
6. Sources (with clickable links)
7. Tool Trace (collapsible debug view)

### 3.2 Agent Orchestrator Service (LangChain)

**Core Responsibilities:**

- **Intent Detection** — Classify incoming prompts into digest types: daily_digest, weekly_report, risk_alert, competitor_monitor
- **Tool Selection & Sequencing** — Determine which MCP tools to call and in what order based on detected intent
- **Structured Digest Composer** — Aggregate raw article data into a standardized digest format with sections
- **Guardrails (No Hallucinations)** — Every claim in the digest must be traceable to a source article. If no articles are found, say so explicitly. Never fabricate competitor intelligence.
- **Audit Logging** — Log every tool call, its input/output, latency, and the final digest to the traceability store

**Digest Output Schema:**

```json
{
  "digest_type": "weekly_report",
  "query": "Anything important about Walmart Connect this week?",
  "generated_at": "2026-03-01T12:00:00Z",
  "report_id": "rpt_abc123",
  "executive_summary": "string",
  "key_signals": [
    {
      "signal": "string",
      "source_url": "string",
      "source_title": "string",
      "published_date": "string",
      "relevance": "high | medium | low"
    }
  ],
  "risks": [
    { "description": "string", "severity": "high | medium | low", "source_urls": ["string"] }
  ],
  "opportunities": [
    { "description": "string", "confidence": "high | medium | low", "source_urls": ["string"] }
  ],
  "action_items": [
    { "action": "string", "priority": "P0 | P1 | P2", "rationale": "string" }
  ],
  "sources": [
    { "url": "string", "title": "string", "published_date": "string", "snippet": "string" }
  ],
  "tool_trace": [
    {
      "tool_name": "string",
      "input": {},
      "output_summary": "string",
      "latency_ms": 0,
      "timestamp": "string"
    }
  ]
}
```

**Agent Pipeline Steps:**

1. Receive prompt from Web App via `POST /digest`
2. Detect intent and extract entities (company names, time ranges, topics)
3. Plan tool calls (which SerpApi queries to make)
4. Execute tool calls via MCP Wrapper
5. Cluster returned articles by topic/theme
6. Extract key signals from article clusters
7. Identify risks and opportunities
8. Generate action items
9. Compose structured digest
10. Log full tool trace to Traceability Store
11. Return structured digest JSON to Web App

### 3.3 MCP Wrapper

**Protocol:** Model Context Protocol (MCP) server exposing tools to the Agent Orchestrator

**Core Responsibilities:**

- **Holds API Key** — Securely stores and injects the SerpApi API key; never exposes it to the agent or client
- **Input Validation** — Validates and sanitizes all tool call inputs before forwarding to SerpApi
- **Response Normalization** — Transforms raw SerpApi responses into a normalized JSON schema the agent can reliably consume
- **Caching** — Caches identical queries within a configurable TTL to reduce API costs and latency
- **Rate Limiting** — Enforces per-minute and per-day rate limits against SerpApi to prevent quota exhaustion
- **Error Formatting** — Returns structured error objects with error codes, messages, and retry guidance

**Exposed MCP Tools:**

| Tool Name | Description | Input | Output |
|-----------|-------------|-------|--------|
| `search_news` | Search recent news articles for a query | `{ query: string, time_range?: string, num_results?: number }` | Normalized article list |
| `search_company_news` | Search news specific to a company | `{ company: string, time_range?: string, topics?: string[] }` | Normalized article list |
| `get_article_metadata` | Fetch metadata for a specific article URL | `{ url: string }` | Title, date, author, snippet |

**Normalized Article Schema:**

```json
{
  "articles": [
    {
      "title": "string",
      "url": "string",
      "source": "string",
      "published_date": "string",
      "snippet": "string",
      "thumbnail_url": "string | null"
    }
  ],
  "query": "string",
  "total_results": 0,
  "cached": false,
  "request_id": "string"
}
```

**SerpApi Integration Details:**

- **Endpoint:** `https://serpapi.com/search`
- **Engine:** `google_news` for news-specific searches
- **Parameters:** `q` (query), `tbm=nws` (news tab), `tbs` (time range), `num` (result count), `gl` (geolocation)
- **Authentication:** API key passed as `api_key` parameter

### 3.4 Traceability Store

**Purpose:** Full audit trail for every digest generated, enabling compliance, debugging, and performance monitoring.

**Storage Schema:**

- **reports** — `report_id`, `digest_type`, `query`, `generated_at`, `digest_json`, `user_id`
- **tool_calls** — `call_id`, `report_id`, `tool_name`, `input_json`, `output_json`, `latency_ms`, `timestamp`, `status`
- **sources** — `source_id`, `report_id`, `url`, `title`, `published_date`, `snippet`, `accessed_at`

**Queryable Dimensions:**

- Tool call logs per report
- Latency metrics (p50, p95, p99) per tool
- Source frequency and recency
- Report generation history per user

---

## 4. Example Flow

> **Prompt:** "Anything important about Walmart Connect this week?"

**Step 1 — Ops Team Prompt**
An ops team member opens the SignalOps web app and types: "Anything important about Walmart Connect this week?"

**Step 2 — Agent Orchestrator Detects Intent**
The Agent Orchestrator classifies this as a `weekly_report` intent for entity "Walmart Connect" with time range "past 7 days." It plans the following tool calls:
- `search_company_news({ company: "Walmart Connect", time_range: "7d" })`
- `search_news({ query: "Walmart Connect retail media", time_range: "7d" })`

**Step 3 — MCP Validates and Normalizes**
The MCP Wrapper validates the inputs, checks the cache (miss), forwards to SerpApi, and normalizes the raw response into the standard article schema. Rate limits are checked and decremented.

**Step 4 — Agent Processes Results**
The Agent Orchestrator:
- Clusters returned articles by topic (e.g., "ad platform updates," "partnership news," "earnings mentions")
- Extracts key signals from each cluster
- Identifies risks (e.g., "Walmart Connect expanding self-serve, may pressure competitor ad margins")
- Identifies opportunities (e.g., "New API integrations announced, potential partnership opening")
- Generates prioritized action items
- Produces the full structured digest
- Logs the complete tool trace to the Traceability Store

**Step 5 — Web UI Displays Digest**
The Web App renders the structured digest:
- **Executive Summary** — 2-3 sentence overview of the week's most important Walmart Connect developments
- **Key Signals** — Ranked list of notable events with source links
- **Risks** — Identified threats with severity ratings
- **Opportunities** — Potential strategic openings with confidence levels
- **Action Items** — Prioritized next steps for the ops team
- **Sources** — All referenced articles with links
- **Tool Trace** — Collapsible debug view showing all tool calls, inputs, outputs, and latencies

---

## 5. Non-Functional Requirements

### 5.1 Performance
- Digest generation: < 30 seconds for standard queries
- SerpApi round-trip (via MCP): < 5 seconds per call
- Web App time-to-first-byte: < 200ms

### 5.2 Reliability
- MCP Wrapper graceful degradation: return cached results if SerpApi is down
- Agent retry logic: up to 3 retries with exponential backoff on transient failures
- Circuit breaker on SerpApi after 5 consecutive failures

### 5.3 Security
- SerpApi key stored in environment variables, never in code or logs
- All API communication over HTTPS
- Input sanitization on all user-facing inputs
- No PII stored in traceability logs

### 5.4 Observability
- Structured JSON logging across all services
- Request correlation IDs propagated through the full pipeline
- Latency histograms per tool call type
- Error rate dashboards per component

---

## 6. Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + TypeScript, Tailwind CSS, Vite |
| Agent Orchestrator | Python 3.11+, LangChain, LangGraph |
| MCP Wrapper | Python 3.11+, MCP SDK (`mcp` package) |
| News API | SerpApi (Google News engine) |
| Database | PostgreSQL 16 |
| Containerization | Docker, Docker Compose |
| Testing | Pytest (Python), Vitest (React) |
| Linting | Ruff (Python), ESLint + Prettier (TypeScript) |

---

## 7. Repository Structure

```
signalops/
├── .claude/
│   └── rules/
│       ├── 00-project-overview.md        # Shared context for all agents
│       ├── 01-web-app-agent.md           # Web App agent rules
│       ├── 02-agent-orchestrator-agent.md # Orchestrator agent rules
│       ├── 03-mcp-wrapper-agent.md       # MCP Wrapper agent rules
│       ├── 04-traceability-store-agent.md # Traceability Store agent rules
│       └── 05-integration-agent.md       # Cross-component integration rules
├── PRD.md
├── packages/
│   ├── web-app/                          # React frontend
│   ├── agent-orchestrator/               # LangChain agent service
│   ├── mcp-wrapper/                      # MCP server for SerpApi
│   └── traceability-store/               # DB schemas and query layer
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 8. Development Workflow

Each component is developed by a dedicated Claude Code agent running in its own git worktree in a RALPH loop (Read → Act → Log → Push → Halt). Agents work in parallel on feature branches and merge through pull requests.

### Agent Assignments

| Agent | Worktree Branch | Scope |
|-------|----------------|-------|
| `web-app-agent` | `feat/web-app` | `packages/web-app/` |
| `agent-orchestrator-agent` | `feat/agent-orchestrator` | `packages/agent-orchestrator/` |
| `mcp-wrapper-agent` | `feat/mcp-wrapper` | `packages/mcp-wrapper/` |
| `traceability-store-agent` | `feat/traceability-store` | `packages/traceability-store/` |
| `integration-agent` | `feat/integration` | `docker-compose.yml`, API contracts, E2E tests |

---

## 9. Milestones

### Phase 1 — Foundation (Weeks 1-2)
- [ ] Scaffold all packages with base configurations
- [ ] MCP Wrapper with SerpApi integration and caching
- [ ] Traceability Store schema and basic CRUD
- [ ] Agent Orchestrator with intent detection and single-tool execution
- [ ] Web App with chat input and raw JSON display

### Phase 2 — Core Pipeline (Weeks 3-4)
- [ ] Full agent pipeline: intent → tool calls → article clustering → digest composition
- [ ] Structured digest rendering in Web App
- [ ] Tool trace logging and debug panel
- [ ] Guardrails: source attribution enforcement, hallucination prevention

### Phase 3 — Polish & Reliability (Weeks 5-6)
- [ ] Streaming digest delivery (SSE)
- [ ] Caching layer optimization
- [ ] Error handling and retry logic
- [ ] Rate limiting dashboard
- [ ] End-to-end integration tests
- [ ] Performance benchmarking

---

## 10. Open Questions

1. Should digests support scheduled/recurring generation (e.g., auto-send daily digest at 8am)?
2. Do we need multi-user support with per-user query history in v1?
3. Should the MCP Wrapper support additional news APIs beyond SerpApi for redundancy?
4. What is the retention policy for traceability data?
