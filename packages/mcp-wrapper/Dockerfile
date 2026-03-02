# ── Stage 1: build ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests first for better layer caching
COPY pyproject.toml ./

# Install all dependencies (including dev extras for potential test runs)
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[dev]"

# Copy source
COPY src/ ./src/

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="SignalOps Team"
LABEL description="SignalOps MCP Wrapper — SerpApi gateway with validation, caching, and rate limiting"

WORKDIR /app

# Create a non-root user for security
RUN groupadd --gid 1001 mcpuser \
    && useradd --uid 1001 --gid mcpuser --shell /bin/sh --create-home mcpuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source
COPY --from=builder /app/src ./src

# Set ownership
RUN chown -R mcpuser:mcpuser /app

USER mcpuser

# ── Environment defaults ──────────────────────────────────────────────────────
ENV MCP_TRANSPORT=sse \
    MCP_SSE_PORT=8001 \
    CACHE_TTL_SECONDS=900 \
    CACHE_TTL_METADATA_SECONDS=3600 \
    RATE_LIMIT_PER_MINUTE=30 \
    RATE_LIMIT_PER_DAY=1000 \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:${MCP_SSE_PORT}/sse', timeout=5)" || exit 1

ENTRYPOINT ["python", "-m", "src.main"]
