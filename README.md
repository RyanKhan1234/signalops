# SignalOps

**A personal research tool that fans out across 16 tools to investigate any topic — powered by a LangChain + LangGraph agentic pipeline with personalized context.**

I built SignalOps to replace my tab-heavy research workflow. Instead of manually piecing together news, Reddit threads, academic papers, GitHub activity, and YouTube talks, I type a question and get a structured digest with every source cited, every tool call visible, and every step of the agent's reasoning exposed. The tool knows who I am, so it tailors what it finds and what it highlights.

---

## What it does

Type any research question:

```
"Deep dive on AI agents"
"What's new with Anthropic this week?"
"Any risks or controversies around sports betting regulation?"
"What's trending in open-source AI right now?"
```

The agent classifies your intent, runs a multi-phase research loop (gathering data, then analyzing it with sentiment analysis, entity extraction, trend calculation, and source comparison), and composes a structured digest:

| Section | What it contains |
|---------|-----------------|
| **Overview** | 2–3 sentence summary of what was found |
| **Key Findings** | Notable developments, each linked to its source |
| **Heads Up** | Concerns or shifts worth watching |
| **Worth Exploring** | Interesting angles and threads to pull on |
| **Next Steps** | Concrete follow-ups — what to do with this information |
| **Sources** | Every article referenced, with publisher and date |
| **Tool Trace** | Every tool call the agent made — inputs, outputs, latency |

Every claim links to a real source. If nothing relevant was found, it says so — no fabrication.

### Personalized Research

SignalOps includes a **user context** feature. You write about yourself — what you're working on, what you care about, what you're trying to figure out — and the agent uses that to decide which tools to call, what search queries to run, and how to frame findings for you specifically.

This isn't just a chatbot system prompt. The context changes the agent's actual *behavior*: which tools it selects, what it searches for, which findings it flags as important, and what next steps it suggests. The same query produces different research paths for different users.

---

## Architecture

```
Browser → React (Web App)
              ↓ POST /digest
      Agent Orchestrator  ←→  LangChain + LangGraph + OpenAI GPT-4o-mini
              ↓                        ↓
        MCP Wrapper             Traceability Store
   (16 tools, 5+ data sources)  (PostgreSQL — full audit log + user profiles)
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
  → fetch_user_context   # Load personalized context from user profile
  → detect_intent        # Classify query → typed DetectedIntent
  → agentic_research     # Multi-phase tool-calling loop (LangChain + OpenAI)
  → process_articles     # Deduplicate, cluster, extract findings
  → compose_digest       # Generate structured digest from clusters
  → validate_guardrails  # Every claim must trace to a real source URL
  → log_trace            # Full report + tool trace written to PostgreSQL
[END]
```

### Intent Detection

The first node uses GPT-4o-mini via LangChain to classify the query and extract entities:

```python
class DetectedIntent(BaseModel):
    intent_type: Literal["latest_news", "deep_dive", "risk_scan", "trend_watch"]
    entities: list[str]    # e.g. ["AI agents", "LangChain"]
    time_range: str        # e.g. "7d"
    original_query: str
```

### Agentic Research Loop

Unlike a static planner, the research node is a **multi-round autonomous loop**. The LLM (via LangChain's `ChatOpenAI.bind_tools()`) decides which tools to call, inspects results, reasons about gaps, and iterates through four phases:

1. **Memory & Discovery** — check past research, cast a wide net with search tools
2. **Contextual Depth** — GitHub activity, financial data, academic papers, trend calculation
3. **Deep Analysis** — fetch and read key articles, run sentiment analysis, extract entities
4. **Cross-Reference** — compare sources for agreement/divergence, follow up on discovered entities

The loop enforces a minimum of 8 different tool types and 2+ analytical tools per task.

### Source Credibility Scoring

Concerns automatically get a credibility rating based on which outlets sourced them:

```python
_HIGH_CREDIBILITY_OUTLETS = {"reuters", "bloomberg", "ap", "bbc", ...}

def _score_source_credibility(source_urls, url_to_article):
    outlets = {get_outlet(url) for url in source_urls}
    if outlets & _HIGH_CREDIBILITY_OUTLETS:
        return "high"
    if len(outlets) >= 3:
        return "high"   # corroborated by 3+ independent sources
    ...
```

### Guardrails

Before the digest is returned, a validation pass checks that every finding, concern, and angle cites a URL that was actually returned by a tool call. If the LLM included a claim without a traceable source, it's dropped and composition retries (max 2 attempts). This is enforced as graph logic, not a prompt instruction.

---

## Tool Inventory

The MCP Wrapper exposes 16 tools in two categories. The agent dynamically selects which to use based on the query, intent, and user context.

### Data Gathering (11 tools)

| Tool | Source | What it does |
|------|--------|-------------|
| `search_news` | Google News (SerpApi) | Recent news articles for any query |
| `search_company_news` | Google News (SerpApi) | News filtered to a specific company |
| `search_web` | Google Web (SerpApi) | Organic web results — analyses, blog posts, docs |
| `search_reddit` | Reddit JSON API | Posts and discussions |
| `search_quora` | Google + site filter | Q&A content from Quora |
| `search_scholar` | Google Scholar (SerpApi) | Academic papers and research |
| `search_github` | GitHub REST API | Repositories sorted by stars |
| `find_videos` | YouTube (SerpApi) | Video talks, demos, explainers |
| `search_finance` | Google Finance (SerpApi) | Market data and financial overview |
| `get_article_metadata` | Google News (SerpApi) | Metadata lookup for a specific URL |
| `fetch_page` | Direct HTTP (httpx) | Fetch and extract plain text from any URL |

### Analytical (5 tools)

| Tool | What it computes | When to use |
|------|------------------|-------------|
| `analyze_sentiment` | Sentiment score, confidence, key phrases | After fetching articles — quantify the tone |
| `extract_entities` | Companies, people, tech, money, tickers | After fetching — discover names and numbers to follow up on |
| `compare_sources` | Cross-source similarity, shared/unique terms | After gathering URLs — find where sources agree or diverge |
| `query_past_research` | Past SignalOps reports | At the start — check what's been covered before |
| `calculate_trend` | Mention frequency across 24h/7d/30d | Quantify whether something is gaining or losing steam |

All tools share the same middleware stack: **validate → cache → rate limit → API → normalize → cache store**.

---

## Running Locally

**Prerequisites:** Docker, Docker Compose, an OpenAI API key, a SerpApi key.

```bash
git clone https://github.com/RyanKhan1234/signalops.git
cd signalops
cp .env.example .env
# Add OPENAI_API_KEY and SERPAPI_API_KEY to .env

docker compose up
```

Open **http://localhost:3001** and try:
- *"Deep dive on AI agents"* — triggers scholar + GitHub + Reddit + web + sentiment + entities
- *"Latest news on Anthropic"* — triggers company news + Reddit + trend calculation
- *"What's trending in open-source AI?"* — triggers videos + GitHub + Reddit + trend + entities

To personalize your research, click **My Context** in the sidebar and tell SignalOps about yourself.

---

## What I Learned

This project was built to go deep on LangChain — not follow tutorials, but design a real agentic pipeline from scratch.

- **LangGraph state machines** — agent graphs with conditional edges, retry loops, and short-circuit exits rather than linear chains
- **LangChain tool binding** — `ChatOpenAI.bind_tools()` for autonomous multi-round tool selection with LangChain message types (`SystemMessage`, `AIMessage`, `ToolMessage`)
- **MCP protocol** — connecting a LangChain agent to a custom MCP server as the tool boundary; the orchestrator never holds data-source API keys
- **Analytical tool design** — building NLP tools (sentiment, entities, source comparison, trend calculation) that run locally and give the agent something to reason about beyond raw search results
- **Personalized agent behavior** — user context that changes tool selection and prompt framing, not just output tone
- **Guardrail patterns** — enforcing source attribution as graph-level logic (loop back on failure) rather than a prompt instruction that can be ignored
- **Multi-API normalization** — unifying responses from SerpApi, GitHub REST, Reddit JSON, and direct HTTP fetches into a single `NormalizedResponse` schema

---

## License

MIT
