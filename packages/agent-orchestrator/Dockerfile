# Agent Orchestrator — Multi-stage Docker build
# Stage 1: builder (installs dependencies)
# Stage 2: runtime (lean production image)

# -----------------------------------------------------------------------
# Stage 1: builder
# -----------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest and install into /app/.venv
COPY pyproject.toml .
RUN pip install --no-cache-dir pip --upgrade && \
    pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir \
        langchain \
        langchain-anthropic \
        langgraph \
        fastapi \
        "uvicorn[standard]" \
        httpx \
        pydantic \
        pydantic-settings \
        anthropic \
        python-dotenv \
        structlog

# -----------------------------------------------------------------------
# Stage 2: runtime
# -----------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY src/ ./src/

# Set ownership
RUN chown -R appuser:appgroup /app

USER appuser

# Environment defaults (override at runtime via docker run -e or .env file)
ENV HOST=0.0.0.0 \
    PORT=8000 \
    LOG_LEVEL=INFO \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Entrypoint
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
