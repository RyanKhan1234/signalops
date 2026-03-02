# Agent Orchestrator Agent Rules

> You are the **agent-orchestrator-agent**. You own `packages/agent-orchestrator/` and work on the `feat/agent-orchestrator` branch.

## Your Scope

You build and maintain the LangChain-based agent orchestration service. This is the brain of SignalOps — it takes natural language prompts, plans tool calls, processes results, and composes structured digests. You do NOT touch the Web App, MCP Wrapper, or Traceability Store packages.

## Tech Stack

- **Language:** Python 3.11+
- **Agent Framework:** LangChain + LangGraph
- **LLM:** Claude (via Anthropic API) — configurable model
- **Web Framework:** FastAPI (exposes `/digest` endpoint)
- **Testing:** pytest + pytest-asyncio
- **Linting:** Ruff

## Package Structure

```
packages/agent-orchestrator/
├── src/
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── orchestrator.py      # Main agent graph definition
│   │   ├── intent.py            # Intent detection and entity extraction
│   │   ├── planner.py           # Tool call planning based on intent
│   │   ├── composer.py          # Structured digest composition
│   │   └── guardrails.py        # Source attribution validation
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py               # FastAPI application
│   │   ├── routes.py            # API route definitions
│   │   └── schemas.py           # Pydantic request/response models
│   ├── tools/
│   │   ├── __init__.py
│   │   └── mcp_client.py        # MCP client to call MCP Wrapper tools
│   ├── models/
│   │   ├── __init__.py
│   │   ├── digest.py            # Digest data models
│   │   └── trace.py             # Tool trace models
│   ├── services/
│   │   ├── __init__.py
│   │   └── traceability.py      # Client for Traceability Store
│   ├── config.py                # Configuration management
│   └── main.py                  # Entrypoint
├── tests/
├── pyproject.toml
├── Dockerfile
└── .env.example
```

## Key Responsibilities

### 1. Intent Detection (`agent/intent.py`)

Classify incoming prompts into one of four digest types and extract structured entities:

| Intent | Trigger Signals | Entity Extraction |
|--------|----------------|-------------------|
| `daily_digest` | "today", "this morning", "overnight", "daily" | Company names, topics |
| `weekly_report` | "this week", "weekly", "past 7 days" | Company names, topics |
| `risk_alert` | "risk", "threat", "concern", "watch out" | Company names, threat vectors |
| `competitor_monitor` | "new competitor", "emerging", "who else" | Industry/segment, geography |

Use structured output from the LLM to extract:
```python
class DetectedIntent(BaseModel):
    intent_type: Literal["daily_digest", "weekly_report", "risk_alert", "competitor_monitor"]
    entities: list[str]           # Company names, topics
    time_range: str               # e.g., "1d", "7d", "30d"
    original_query: str
```

### 2. Tool Call Planning (`agent/planner.py`)

Based on the detected intent, plan which MCP tools to call:

- `daily_digest` → `search_company_news(time_range="1d")` per entity
- `weekly_report` → `search_company_news(time_range="7d")` + `search_news(broader query, time_range="7d")`
- `risk_alert` → `search_company_news(time_range="1d")` + `search_news(risk-oriented query)`
- `competitor_monitor` → `search_news(industry/segment query, time_range="30d")`

The planner outputs an ordered list of tool calls. Multiple calls may run in parallel where there are no dependencies.

### 3. Article Processing Pipeline

After tool calls return articles, process them through this pipeline:

1. **Deduplication** — Remove duplicate articles (by URL) across tool call results
2. **Clustering** — Group articles by topic/theme using LLM-based classification
3. **Signal Extraction** — For each cluster, extract the key signal (what happened, why it matters)
4. **Risk Identification** — Identify articles that indicate competitive threats
5. **Opportunity Detection** — Identify articles that suggest strategic openings
6. **Action Item Generation** — Synthesize prioritized action items from signals + risks + opportunities

### 4. Structured Digest Composition (`agent/composer.py`)

Compose the final digest from processed article data. The composer MUST:

- Write a concise executive summary (2-3 sentences max)
- Rank key signals by relevance
- Assign severity to risks and confidence to opportunities
- Prioritize action items (P0 = act now, P1 = this week, P2 = track)
- Include source URLs for every claim
- Generate the tool trace from logged call data

### 5. Guardrails (`agent/guardrails.py`)

**This is the most critical module.** Enforce:

- **Source Attribution** — Every `key_signal`, `risk`, and `opportunity` MUST have at least one `source_url` that was actually returned by a tool call. If a signal cannot be attributed, it is dropped.
- **No Hallucination** — The agent must not invent facts, company names, dates, or metrics that do not appear in source articles.
- **Empty Result Handling** — If no articles are found, return a digest with `executive_summary: "No relevant articles found for this query in the specified time range."` and empty arrays for all other fields.
- **Validation** — Before returning, validate the entire digest against the schema. Every URL in the digest must exist in the `sources` array.

### 6. API Layer (`api/`)

**Single endpoint:**

```
POST /digest
Content-Type: application/json

{
  "prompt": "Anything important about Walmart Connect this week?"
}

Response: DigestResponse (see PRD for full schema)
```

- FastAPI with async endpoints
- Request validation via Pydantic
- Structured error responses matching the shared error format
- `X-Request-ID` header propagation
- Health check at `GET /health`

### 7. Traceability Client (`services/traceability.py`)

After each digest is generated, send the full report + tool trace to the Traceability Store:

```python
async def log_report(report: DigestResponse) -> None:
    """Log completed digest and all tool calls to traceability store."""

async def log_tool_call(call: ToolTraceEntry, report_id: str) -> None:
    """Log individual tool call (called during execution)."""
```

## Agent Graph (LangGraph)

```
[START] → [detect_intent] → [plan_tools] → [execute_tools] → [process_articles] → [compose_digest] → [validate_guardrails] → [log_trace] → [END]
```

- `execute_tools` supports parallel execution of independent tool calls
- `validate_guardrails` can loop back to `compose_digest` if validation fails (max 2 retries)
- All nodes log to the tool trace

## MCP Client Configuration

Connect to the MCP Wrapper as an MCP client:

```python
# The MCP Wrapper runs as a separate service
MCP_WRAPPER_URL = os.getenv("MCP_WRAPPER_URL", "http://localhost:8001")
```

Use the LangChain MCP tool integration or a custom MCP client to invoke tools exposed by the MCP Wrapper.

## Rules

1. **Every claim needs a source.** This is non-negotiable. If you cannot attribute a statement to a source article, do not include it.
2. **Never call SerpApi directly.** Always go through the MCP Wrapper. The orchestrator does not hold API keys.
3. **Log everything.** Every tool call input, output, and latency must be captured in the tool trace.
4. **Fail gracefully.** If the MCP Wrapper is down, return an error digest explaining the issue — never hang or crash.
5. **Keep prompts in code, not in the LLM.** System prompts and prompt templates live in version-controlled Python files, not in a database or external service.
6. **Type everything.** All public functions have type hints. All data structures are Pydantic models.
7. **Async by default.** All I/O operations (API calls, DB writes) must be async.
