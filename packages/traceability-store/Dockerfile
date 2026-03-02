# Traceability Store — production Docker image
#
# Multi-stage build:
#   1. builder  — install dependencies into a virtual env
#   2. runtime  — copy the venv and source into a slim image

# ── Stage 1: dependency builder ───────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps for asyncpg (C extension)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create an isolated virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies first (layer-cached if pyproject.toml unchanged)
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ".[dev]" --no-deps || true && \
    pip install --no-cache-dir \
        fastapi \
        "uvicorn[standard]" \
        "sqlalchemy[asyncio]" \
        asyncpg \
        alembic \
        pydantic \
        pydantic-settings \
        python-dotenv

# ── Stage 2: runtime image ────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY src/ ./src/
COPY alembic.ini .

# Ensure migrations directory is present
# (migrations are run separately via `alembic upgrade head` before startup)

# Set ownership
RUN chown -R appuser:appgroup /app

USER appuser

# Expose the API port
EXPOSE 8002

# Health check — relies on the /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')" || exit 1

# Default command — run database migrations then start the server
# In production, migrations should be run as a separate init container or job.
# This CMD is a convenience for simple single-container deployments.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]
