# SignalOps

**A personal news research tool powered by a LangChain agent.**

I built SignalOps because I wanted a better way to research topics I actually care about — AI developments, market trends, whatever I'm currently curious about. Instead of opening a dozen tabs and manually piecing things together, I type a question and get a structured breakdown with every source visible and every step of the agent's reasoning exposed.

The data comes from real-time public news (via SerpApi). The value is in how the agent structures, attributes, and surfaces it.

---

## Why I built this

When I'm researching something — a new AI release, an emerging trend, anything — my workflow used to be:
- open tabs
- skim articles
- try to mentally connect the dots
- lose track of where things came from

I wanted something that would do the gathering and structuring for me, while staying completely transparent about its sources and how it reached its conclusions. I also wanted a real project to go deep on LangChain — not just follow tutorials, but actually design an agent pipeline from scratch.

SignalOps was the answer to both.

---

## What it does

Type a natural language question:

```text
"What's new in AI model releases this week?"
"Any major developments in sports betting regulation lately?"
"Give me a breakdown of what's happening with Shopify."
```

SignalOps runs a LangChain agent that searches for relevant news, processes the results, and returns a structured digest:

- **Executive Summary** — 2-3 sentence overview
- **Key Signals** — notable developments, each linked to its source article
- **Risks** — concerns or threats flagged with severity
- **Opportunities** — relevant openings or tailwinds
- **Action Items** — prioritized next steps if applicable
- **Sources** — every article referenced, with title, publisher, and date
- **Tool Trace** — every search query the agent ran, what it returned, and how long it took

Every claim links back to a real article. If nothing relevant was found, it says so — no fabrication.

---

## How the LangChain agent works

The core of SignalOps is a **LangGraph agent graph** in the `agent-orchestrator` package. This was the main thing I wanted to build — a real agentic pipeline with structured outputs, tool use, guardrails, and full observability.

### Agent graph

```
[START]
  → detect_intent        # LLM classifies the query and extracts entities (structured output)
  → plan_tools           # Decides which searches to run and in what order
  → execute_tools        # Runs searches in parallel where possible
  → process_articles     # Deduplicates, clusters, and extracts signals
  → compose_digest       # LLM composes the structured digest from processed articles
  → validate_guardrails  # Enforces source attribution — loops back if a claim can't be traced
  → log_trace            # Persists the report and full tool trace
[END]
```

### Intent detection

The first node uses Claude with **structured output** (via LangChain's `.with_structured_output()`) to classify the query and extract what to search for:

```python
class DetectedIntent(BaseModel):
    intent_type: Literal["daily_digest", "weekly_report", "risk_alert", "competitor_monitor"]
    entities: list[str]
    time_range: str
    original_query: str
```

Using the LLM to produce a typed schema rather than prose was one of the more useful patterns I learned here — it makes the rest of the graph reliable.

### Tool use via MCP

The agent doesn't call SerpApi directly. It calls tools exposed by a separate `mcp-wrapper` service over MCP (Model Context Protocol). That service handles caching, rate limiting, and normalizing raw API responses before the agent ever sees them.

LangChain's tool integration captures every call's inputs, outputs, and latency automatically, which populates the tool trace shown in the UI.

### Guardrails

Before the digest is returned, a validation pass checks that every signal, risk, and opportunity cites a URL that was actually returned by a tool call. If the LLM included a claim without a traceable source, it's dropped and composition retries. This is enforced as graph logic, not just a prompt instruction.

---

## Architecture

```
Browser → React (Web App)
            ↓ POST /digest
       Agent Orchestrator  ←→  LangChain + LangGraph + Claude
            ↓                        ↓
       MCP Wrapper                Traceability Store
       (news search via SerpApi)  (PostgreSQL)
```

| Component | Stack |
|---|---|
| Web App | React 18, TypeScript, Vite, Tailwind CSS |
| Agent Orchestrator | Python 3.11, LangChain, LangGraph, FastAPI |
| MCP Wrapper | Python 3.11, MCP SDK, httpx, in-memory cache |
| Traceability Store | Python 3.11, FastAPI, SQLAlchemy 2.0, PostgreSQL 16 |

**Data source:** public news via SerpApi (Google News). The intelligence layer is the structured analysis pipeline built on top of it.

---

## Running locally

**Prerequisites:** Docker, Docker Compose, an Anthropic API key, a SerpApi key.

```bash
# Clone and configure
git clone <repo-url>
cd signalops
cp .env.example .env
# Fill in ANTHROPIC_API_KEY and SERPAPI_API_KEY in .env

# Start the full stack
docker compose up

# Open the app
open http://localhost:3000
```

---

## What I learned

This project was primarily a vehicle for going deep on LangChain. Key things I worked through:

- **LangGraph state machines** — designing agent graphs with conditional edges and retry loops rather than linear chains
- **Structured outputs** — using `.with_structured_output()` for reliable typed responses instead of parsing prose
- **Tool tracing** — capturing every tool call's inputs, outputs, and latency within the graph for full observability
- **Guardrail patterns** — enforcing output constraints as graph-level logic, not just prompt instructions
- **MCP integration** — connecting a LangChain agent to an MCP server for clean tool abstraction
- **Async agent execution** — running independent tool calls in parallel within a LangGraph graph
