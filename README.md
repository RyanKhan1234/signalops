# SignalOps

**AI-powered personal intelligence system for structured, source-attributed research.**

SignalOps is a tool I built to improve how I personally research and understand complex topics — and to deepen my hands-on experience with LangChain and agentic AI systems.

When I look into something — whether it's a company, product, or trend — I don't just want a summary. I want:
- clear signals  
- trustworthy sources  
- structured insights  
- and visibility into how conclusions were formed  

Most tools give answers.  
SignalOps gives you **answers + reasoning + sources**.

---

## Why I built this

My typical research workflow used to look like:
- open multiple tabs  
- skim articles  
- manually piece together insights  
- lose track of sources  

This made it hard to trust conclusions, trace where insights came from, or understand how different signals connect.

SignalOps replaces that with a structured agent pipeline that:
- gathers relevant data via real-time news search  
- analyzes and clusters articles by theme  
- attributes every claim to a source  
- exposes the full reasoning process — every tool call, every decision  

It also became the project I used to learn LangChain deeply. The agent orchestration layer is built on **LangChain + LangGraph**, and building it forced me to understand how to design multi-step agent graphs, manage tool call tracing, handle retries, and enforce output guarantees — things you don't get from tutorials.

---

## What it does

You give SignalOps a natural language prompt:

```text
"Anything important about Walmart Connect this week?"
"What are the biggest risks around OpenAI right now?"
"Give me a daily digest on Shopify."
```

SignalOps returns a **structured intelligence digest**:

- **Executive Summary** — 2-3 sentence overview of what matters
- **Key Signals** — notable developments, each linked to its source article
- **Risks** — threats or concerns flagged with severity
- **Opportunities** — strategic openings with confidence indicators
- **Action Items** — prioritized (P0/P1/P2) next steps
- **Sources** — every referenced article with title, publisher, and date
- **Tool Trace** — a full log of every search query run, what it returned, and how long it took

Every claim in the digest is traceable to a real article. If no relevant articles exist, the system says so — it never fabricates intelligence.

---

## How the LangChain agent works

The core of SignalOps is a **LangGraph agent graph** in the `agent-orchestrator` package. I built this to get hands-on with the full LangChain ecosystem — not just basic chains, but real agentic workflows with structured outputs, tool use, guardrails, and traceability.

### Agent graph

```
[START]
  → detect_intent        # LLM-powered intent + entity extraction (structured output)
  → plan_tools           # Decide which MCP tools to call and in what order
  → execute_tools        # Run tool calls (parallel where possible)
  → process_articles     # Deduplicate, cluster, extract signals
  → compose_digest       # LLM composes the structured digest from processed articles
  → validate_guardrails  # Enforce source attribution — loop back if validation fails
  → log_trace            # Persist report + tool trace to Traceability Store
[END]
```

Each node is an async LangGraph node. The graph supports conditional edges (e.g., the guardrails node can loop back to re-compose if attribution fails) and parallel tool execution.

### Intent detection

The first node uses Claude with **structured output** (via LangChain's `.with_structured_output()`) to classify the prompt and extract entities:

```python
class DetectedIntent(BaseModel):
    intent_type: Literal["daily_digest", "weekly_report", "risk_alert", "competitor_monitor"]
    entities: list[str]
    time_range: str
    original_query: str
```

This was one of the more interesting LangChain patterns to implement — using the LLM not to generate prose, but to reliably produce a typed schema that the rest of the graph depends on.

### Tool use via MCP

Rather than calling a search API directly, the orchestrator uses an **MCP (Model Context Protocol) client** to call tools exposed by a separate `mcp-wrapper` service. This keeps the agent decoupled from external APIs and gives the tool layer its own caching, rate limiting, and normalization logic.

LangChain's tool integration made it straightforward to bind MCP tools to the agent and capture inputs, outputs, and latency for every call — which feeds directly into the tool trace.

### Guardrails

The guardrails node enforces the core invariant: **every signal, risk, and opportunity must cite a URL that was actually returned by a tool call**. This is implemented as a post-composition validation pass. If the LLM includes a claim without a traceable source, that claim is dropped and the graph retries composition.

This was a deliberate architectural choice — using the graph's conditional edges to build a feedback loop rather than relying on prompt instructions alone.

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

All four services start together. The web app is on `:3000`, the agent orchestrator on `:8000`.

---

## What I learned

This project was primarily a vehicle for going deeper on LangChain. Key things I worked through:

- **LangGraph state machines** — designing agent graphs with conditional edges and retry loops rather than linear chains
- **Structured outputs** — using `.with_structured_output()` for reliable typed responses instead of parsing prose
- **Tool tracing** — capturing every tool call's inputs, outputs, and latency within the graph for full observability
- **Guardrail patterns** — enforcing output constraints as graph-level logic, not just prompt instructions
- **MCP integration** — connecting a LangChain agent to an MCP server for clean tool abstraction
- **Async agent execution** — running independent tool calls in parallel within a LangGraph graph
