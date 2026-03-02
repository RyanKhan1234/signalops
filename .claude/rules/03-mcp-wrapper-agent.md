# MCP Wrapper Agent Rules

> You are the **mcp-wrapper-agent**. You own `packages/mcp-wrapper/` and work on the `feat/mcp-wrapper` branch.

## Your Scope

You build and maintain the MCP server that wraps SerpApi. This service is the sole gateway to external news data. You do NOT touch the Web App, Agent Orchestrator, or Traceability Store packages.

## Tech Stack

- **Language:** Python 3.11+
- **MCP Framework:** `mcp` Python SDK (Model Context Protocol)
- **HTTP Client:** `httpx` (async)
- **Caching:** In-memory (TTL-based) via `cachetools`, with optional Redis upgrade path
- **Testing:** pytest + pytest-asyncio
- **Linting:** Ruff

## Package Structure

```
packages/mcp-wrapper/
├── src/
│   ├── server.py              # MCP server definition and tool registration
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── search_news.py          # search_news tool implementation
│   │   ├── search_company_news.py  # search_company_news tool implementation
│   │   └── get_article_metadata.py # get_article_metadata tool implementation
│   ├── serpapi/
│   │   ├── __init__.py
│   │   ├── client.py          # SerpApi HTTP client
│   │   ├── models.py          # Raw SerpApi response models
│   │   └── normalizer.py      # Response normalization to standard schema
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── validator.py       # Input validation
│   │   ├── cache.py           # Caching layer
│   │   ├── rate_limiter.py    # Rate limiting
│   │   └── error_handler.py   # Structured error formatting
│   ├── config.py              # Configuration management
│   └── main.py                # Entrypoint
├── tests/
│   ├── test_tools/
│   ├── test_serpapi/
│   ├── test_middleware/
│   └── fixtures/              # Sample SerpApi responses for testing
├── pyproject.toml
├── Dockerfile
└── .env.example
```

## Key Responsibilities

### 1. MCP Server (`server.py`)

Register three MCP tools that the Agent Orchestrator can call:

```python
from mcp.server import Server
from mcp.types import Tool

server = Server("signalops-news")

# Register tools
@server.tool()
async def search_news(query: str, time_range: str = "7d", num_results: int = 10) -> dict:
    """Search recent news articles for a query."""

@server.tool()
async def search_company_news(company: str, time_range: str = "7d", topics: list[str] | None = None) -> dict:
    """Search news specific to a company."""

@server.tool()
async def get_article_metadata(url: str) -> dict:
    """Fetch metadata for a specific article URL."""
```

The MCP server communicates via stdio or SSE transport (configurable).

### 2. SerpApi Client (`serpapi/client.py`)

**Endpoint:** `https://serpapi.com/search`

**Engine:** `google_news`

**Key Parameters:**

| Parameter | Description | Example |
|-----------|------------|---------|
| `q` | Search query | `"Walmart Connect"` |
| `tbm` | Search type | `nws` (news) |
| `tbs` | Time range | `qdr:d` (past day), `qdr:w` (past week), `qdr:m` (past month) |
| `num` | Results count | `10` |
| `gl` | Geolocation | `us` |
| `api_key` | SerpApi key | From environment variable |

**Time Range Mapping:**

| Input | SerpApi `tbs` Value |
|-------|-------------------|
| `"1d"` | `qdr:d` |
| `"7d"` | `qdr:w` |
| `"30d"` | `qdr:m` |
| `"1y"` | `qdr:y` |

**Raw response handling:**
- SerpApi returns JSON with a `news_results` array
- Each result contains: `title`, `link`, `source`, `date`, `snippet`, `thumbnail`
- Handle pagination if needed (via `start` parameter)

### 3. Response Normalization (`serpapi/normalizer.py`)

Transform raw SerpApi responses into the normalized schema:

```python
class NormalizedArticle(BaseModel):
    title: str
    url: str
    source: str                    # e.g., "Reuters", "TechCrunch"
    published_date: str            # ISO 8601
    snippet: str
    thumbnail_url: str | None

class NormalizedResponse(BaseModel):
    articles: list[NormalizedArticle]
    query: str
    total_results: int
    cached: bool
    request_id: str                # UUID for traceability
```

**Normalization rules:**
- Parse relative dates from SerpApi (e.g., "2 hours ago", "3 days ago") into ISO 8601
- Strip HTML entities from titles and snippets
- Deduplicate articles by URL within a single response
- Generate a `request_id` (UUID) for each normalized response

### 4. Input Validation (`middleware/validator.py`)

Validate all tool inputs before forwarding to SerpApi:

- `query` / `company`: Non-empty string, max 200 characters, no injection characters
- `time_range`: Must be one of `1d`, `7d`, `30d`, `1y`
- `num_results`: Integer between 1 and 50
- `topics`: If provided, list of strings, each max 100 characters
- `url` (for metadata): Must be a valid HTTP/HTTPS URL

Return structured validation errors:
```python
class ValidationError(BaseModel):
    code: str = "VALIDATION_ERROR"
    message: str
    field: str
    constraint: str
```

### 5. Caching (`middleware/cache.py`)

Cache SerpApi responses to reduce costs and latency:

- **Cache Key:** Hash of `(tool_name, sorted_params)`
- **Default TTL:** 15 minutes for news searches, 1 hour for article metadata
- **Cache Hit:** Return cached response with `cached: true` in the normalized response
- **Cache Invalidation:** TTL-based only (no manual invalidation needed for v1)
- **Storage:** In-memory `TTLCache` from `cachetools`. Document Redis upgrade path.

### 6. Rate Limiting (`middleware/rate_limiter.py`)

Protect against SerpApi quota exhaustion:

- **Per-minute limit:** 30 requests/minute (configurable via env var)
- **Per-day limit:** 1000 requests/day (configurable via env var)
- **Behavior on limit:** Return a structured error with `retry_after_seconds`
- **Implementation:** Sliding window counter (in-memory for v1)

```python
class RateLimitError(BaseModel):
    code: str = "RATE_LIMIT_EXCEEDED"
    message: str
    retry_after_seconds: int
    limit_type: str  # "per_minute" or "per_day"
```

### 7. Error Handling (`middleware/error_handler.py`)

All errors returned as structured JSON matching the shared error format:

| Error Code | When | HTTP-Equivalent |
|-----------|------|----------------|
| `VALIDATION_ERROR` | Bad input parameters | 400 |
| `RATE_LIMIT_EXCEEDED` | Too many requests | 429 |
| `UPSTREAM_ERROR` | SerpApi returned error or timeout | 502 |
| `UPSTREAM_TIMEOUT` | SerpApi did not respond in time | 504 |
| `INTERNAL_ERROR` | Unexpected failure | 500 |

- SerpApi timeouts: 10-second timeout per request
- SerpApi errors: Parse error response, wrap in structured format
- Network failures: Catch `httpx` exceptions, return `UPSTREAM_ERROR`

## Environment Variables

```bash
SERPAPI_API_KEY=           # Required. SerpApi API key
SERPAPI_BASE_URL=https://serpapi.com/search  # Optional override
CACHE_TTL_SECONDS=900     # Default: 15 minutes
RATE_LIMIT_PER_MINUTE=30
RATE_LIMIT_PER_DAY=1000
MCP_TRANSPORT=stdio       # "stdio" or "sse"
MCP_SSE_PORT=8001         # Port for SSE transport
LOG_LEVEL=INFO
```

## Testing Strategy

- **Unit tests** for each tool, validator, normalizer, cache, and rate limiter
- **Fixture-based**: Store sample SerpApi JSON responses in `tests/fixtures/` and test normalization against them
- **Mock SerpApi**: Never call real SerpApi in tests. Use `httpx` mock or `respx`.
- **Rate limiter tests**: Verify limits are enforced and `retry_after_seconds` is correct
- **Cache tests**: Verify TTL behavior, cache key generation, and `cached` flag in response

## Rules

1. **Never expose the API key.** The SerpApi key lives in environment variables only. It is never logged, returned in responses, or passed to the agent.
2. **Normalize everything.** The agent must never see raw SerpApi JSON. Every response goes through the normalizer.
3. **Validate before you call.** Never send invalid parameters to SerpApi. Validate and reject first.
4. **Cache aggressively.** Identical queries within the TTL window must return cached results.
5. **Rate limit defensively.** Better to reject a request than to burn the entire day's quota.
6. **Log request IDs.** Every SerpApi call gets a request_id that flows through to the normalized response.
7. **No business logic.** The MCP Wrapper does not interpret articles, detect intent, or compose digests. It fetches, normalizes, and returns data. That's it.
