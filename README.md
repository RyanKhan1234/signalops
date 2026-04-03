# SignalOps

**A personal intelligence tool that fans out across 11 data sources in parallel to research any topic — powered by a LangChain + LangGraph agent pipeline.**

I built SignalOps to replace my tab-heavy research workflow. Instead of manually piecing together news, Reddit threads, academic papers, GitHub activity, and YouTube talks, I type a question and get a structured digest with every source cited, every tool call visible, and every step of the agent's reasoning exposed.

---

## What it does

Type any research question:

```
"Deep dive on AI agents"
"What's new with Anthropic this week?"
"Any risks or controversies around sports betting regulation?"
"What's trending in open-source AI right now?"
```

The agent classifies your intent, plans which tools to run (and which can run in parallel), executes them, clusters the results, and composes a structured digest:

| Section | What it contains |
|---------|-----------------|
| **Executive Summary** | 2–3 sentence overview |
| **Key Signals** | Notable developments, each linked to its source |
| **Risks** | Threats and concerns, with severity and source credibility ratings |
| **Opportunities** | Strategic openings or tailwinds |
| **Action Items** | Prioritized next steps |
| **Sources** | Every article referenced, with publisher and date |
| **Tool Trace** | Every tool call the agent made — inputs, outputs, latency |

Every claim links to a real source. If nothing relevant was found, it says so — no fabrication.

---

## Architecture

```
Browser → React (Web App)
              ↓ POST /digest
      Agent Orchestrator  ←→  LangChain + LangGraph + Claude
              ↓                        ↓
        MCP Wrapper             Traceability Store
   (11 tools, 5 data sources)   (PostgreSQL — full audit log)
```

| Component | Stack |
|-----------|-------|
| Web App | React 18, TypeScript, Vite, Tailwind CSS |
| Agent Orchestrator | Python 3.11, LangChain, LangGraph, FastAPI |
| MCP Wrapper | Python 3.11, MCP SDK, httpx, TTL cache, rate limiter |
| Traceability Store | Python 3.11, FastAPI, SQLAlchemy 2.0, PostgreSQL 16 |

---

## The Agent Pipeline

The core of SignalOps is a **LangGraph state graph** in the Agent Orchestrator. Each node is a discrete step; the graph enforces ordering, retries, and short-circuit conditions.

```
[START]
  → detect_intent        # Claude classifies query → typed DetectedIntent
  → plan_tools           # Planner selects tools and groups parallel calls
  → execute_tools        # Parallel async execution across tool groups
  → process_articles     # Deduplicate, cluster, extract signals
  → compose_digest       # Claude composes structured digest from clusters
  → validate_guardrails  # Every claim must trace to a real source URL
  → log_trace            # Full report + tool trace written to PostgreSQL
[END]
```

### Intent Detection

The first node uses Claude with **structured output** to classify the query and extract entities:

```python
class DetectedIntent(BaseModel):
    intent_type: Literal["latest_news", "deep_dive", "risk_scan", "trend_watch"]
    entities: list[str]    # e.g. ["AI agents", "LangChain"]
    time_range: str        # e.g. "7d"
    original_query: str
```

Using `.with_structured_output()` here means every downstream node gets a typed object — no brittle string parsing.

### Smart Tool Routing

The planner uses two heuristics to decide which tools to invoke per entity:

```python
def _is_named_entity(entity: str) -> bool:
    """'OpenAI' → True (routes to search_company_news)
       'AI model releases' → False (routes to search_news)"""
    words = entity.lower().split()
    if len(words) > 3:
        return False
    return not any(w in _TOPIC_WORDS for w in words)

def _is_tech_topic(entity: str) -> bool:
    """'AI agents' → True (adds search_scholar + search_github)
       'sports betting' → False (adds search_quora instead)"""
    return any(w in _TECH_WORDS for w in entity.lower().split())
```

This means a query like *"Deep dive on AI agents and Anthropic"* produces a plan like:

```
search_news          "AI agents"              │
search_web           "AI agents analysis"     │ parallel
search_scholar       "AI agents"              │ group 0
search_github        "AI agents"              │
search_reddit        "AI agents"              │
                                              │
search_company_news  company="Anthropic"      │
search_web           "Anthropic analysis"     │ parallel
search_reddit        "Anthropic"              │ group 0
                                              │
search_news          broader context query    │
```

All 9 calls fire concurrently. The planner caps total calls at 15 to prevent runaway API usage.

### Parallel Execution

Tool calls share a `parallel_group` integer. The MCP client batches same-group calls with `asyncio.gather()`:

```python
for group_id in sorted(groups.keys()):
    group_results = await asyncio.gather(
        *[self.call_tool(call) for call in groups[group_id]]
    )
```

### Source Credibility Scoring

Risks automatically get a credibility rating based on which outlets sourced them and how many corroborate the claim:

```python
_HIGH_CREDIBILITY_OUTLETS = {"reuters", "bloomberg", "ap", "bbc", ...}

def _score_source_credibility(source_urls, url_to_article):
    outlets = {get_outlet(url) for url in source_urls}
    if outlets & _HIGH_CREDIBILITY_OUTLETS:
        return "high"
    if len(outlets) >= 3:
        return "high"   # corroborated by 3+ independent sources
    if len(outlets) == 2:
        return "medium"
    return "low"
```

### Guardrails

Before the digest is returned, a validation pass checks that every signal, risk, and opportunity cites a URL that was actually returned by a tool call. If the LLM included a claim without a traceable source, it's dropped and composition retries (max 2 attempts). This is enforced as graph logic, not a prompt instruction.

---

## The Tool Inventory

The MCP Wrapper exposes 11 tools across 5 data source categories. The planner routes to them based on intent type and entity classification.

### News & Web
| Tool | Source | What it does |
|------|--------|-------------|
| `search_news` | Google News (SerpApi) | Recent news articles for any query |
| `search_company_news` | Google News (SerpApi) | News filtered to a specific company |
| `search_web` | Google Web (SerpApi) | Organic web results — analyses, blog posts, docs |

### Social & Community
| Tool | Source | What it does |
|------|--------|-------------|
| `search_reddit` | Reddit JSON API | Posts and discussions (no API key needed) |
| `search_quora` | Google + site filter | Q&A content from Quora |

### Academic & Technical
| Tool | Source | What it does |
|------|--------|-------------|
| `search_scholar` | Google Scholar (SerpApi) | Academic papers and research |
| `search_github` | GitHub REST API | Repositories sorted by stars (no API key needed) |

### Media
| Tool | Source | What it does |
|------|--------|-------------|
| `find_videos` | YouTube (SerpApi) | Video talks, demos, explainers |

### Financial & Utility
| Tool | Source | What it does |
|------|--------|-------------|
| `search_finance` | Google Finance (SerpApi) | Market data and financial overview |
| `get_article_metadata` | Google News (SerpApi) | Metadata lookup for a specific URL |
| `fetch_page` | Direct HTTP (httpx) | Fetch and extract plain text from any URL |

All tools share the same middleware stack: **validate → cache → rate limit → API → normalize → cache store**.

---

## Running Locally

**Prerequisites:** Docker, Docker Compose, an Anthropic API key, a SerpApi key.

```bash
git clone https://github.com/RyanKhan1234/signalops.git
cd signalops
cp .env.example .env
# Add ANTHROPIC_API_KEY and SERPAPI_API_KEY to .env

docker compose up
```

Open **http://localhost:3001** and try:
- *"Deep dive on AI agents"* — triggers scholar + GitHub + Reddit + web
- *"Latest news on Anthropic"* — triggers company news + Reddit
- *"What's trending in open-source AI?"* — triggers videos + GitHub + Reddit

---

## What I Learned

This project was built to go deep on LangChain — not follow tutorials, but design a real agentic pipeline from scratch.

- **LangGraph state machines** — agent graphs with conditional edges, retry loops, and short-circuit exits rather than linear chains
- **Structured outputs** — `.with_structured_output()` for reliable typed responses; downstream nodes never parse strings
- **MCP protocol** — connecting a LangChain agent to a custom MCP server as the tool boundary; the orchestrator never holds API keys
- **Parallel async tool execution** — `asyncio.gather()` across independent tool groups; wall-clock time is the max single-call latency, not the sum
- **Guardrail patterns** — enforcing source attribution as graph-level logic (loop back on failure) rather than a prompt instruction that can be ignored
- **Tool routing heuristics** — using lightweight string heuristics to make routing decisions without an extra LLM call
- **Multi-API normalization** — unifying responses from SerpApi, GitHub REST, Reddit JSON, and direct HTTP fetches into a single `NormalizedResponse` schema

---

## License

MIT
