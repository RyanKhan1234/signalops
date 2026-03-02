#!/usr/bin/env bash
# SignalOps — One-command project setup
# Usage: ./scripts/setup.sh
#
# This script:
#   1. Checks prerequisites (Docker, Docker Compose, Node, Python)
#   2. Copies .env.example → .env if .env does not exist
#   3. Installs dependencies for all packages
#   4. Builds Docker images
#   5. Starts the full stack
#   6. Runs database migrations via Alembic
#   7. Seeds the traceability store with sample data
#   8. Prints service URLs

set -euo pipefail

# ─── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ─── Helpers ──────────────────────────────────────────────────────────────────
info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ─── Script location ──────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

info "SignalOps setup starting from: ${ROOT_DIR}"
echo ""

# ─── 1. Prerequisite checks ───────────────────────────────────────────────────
info "Checking prerequisites..."

check_command() {
  local cmd="$1"
  local install_hint="$2"
  if ! command -v "${cmd}" &>/dev/null; then
    error "${cmd} is required but not installed. ${install_hint}"
  fi
  success "${cmd} found: $(${cmd} --version 2>&1 | head -1)"
}

check_command "docker"         "Install Docker Desktop: https://docs.docker.com/get-docker/"
check_command "docker"         "Install Docker Desktop: https://docs.docker.com/get-docker/"

# Check docker compose (v2 plugin or v1 standalone)
if docker compose version &>/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
  success "docker compose (v2) found: $(docker compose version --short)"
elif command -v docker-compose &>/dev/null; then
  COMPOSE_CMD="docker-compose"
  success "docker-compose (v1) found: $(docker-compose --version)"
else
  error "Docker Compose is required. Install Docker Desktop or 'pip install docker-compose'."
fi

# Node.js (for local web-app development outside Docker)
if command -v node &>/dev/null; then
  success "node found: $(node --version)"
else
  warn "node not found. This is only needed for local development outside Docker."
fi

# Python (for running e2e tests locally)
if command -v python3 &>/dev/null; then
  PYTHON_CMD="python3"
  success "python3 found: $(python3 --version)"
elif command -v python &>/dev/null; then
  PYTHON_CMD="python"
  success "python found: $(python --version)"
else
  warn "python3 not found. Required to run E2E tests outside Docker."
  PYTHON_CMD=""
fi

echo ""

# ─── 2. Environment file setup ────────────────────────────────────────────────
info "Setting up environment variables..."

if [ ! -f "${ROOT_DIR}/.env" ]; then
  cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
  warn ".env created from .env.example"
  warn "ACTION REQUIRED: Edit ${ROOT_DIR}/.env and fill in:"
  warn "  - ANTHROPIC_API_KEY"
  warn "  - SERPAPI_API_KEY"
  echo ""
  read -r -p "Press ENTER to continue after editing .env, or Ctrl+C to exit and edit it now: "
else
  success ".env already exists, skipping copy"
fi

# Validate required variables are set
source "${ROOT_DIR}/.env"

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  error "ANTHROPIC_API_KEY is not set in .env. Please add it and re-run setup."
fi
if [ -z "${SERPAPI_API_KEY:-}" ]; then
  error "SERPAPI_API_KEY is not set in .env. Please add it and re-run setup."
fi

success "Required environment variables are set"
echo ""

# ─── 3. Install local dependencies (optional, for non-Docker dev) ─────────────
info "Installing package dependencies..."

# Web App
if [ -f "${ROOT_DIR}/packages/web-app/package.json" ] && command -v npm &>/dev/null; then
  info "Installing web-app npm dependencies..."
  npm --prefix "${ROOT_DIR}/packages/web-app" install --silent
  success "web-app dependencies installed"
else
  info "Skipping web-app npm install (package.json not found or npm not available)"
fi

# Python packages — install in virtual envs per package
for pkg in agent-orchestrator mcp-wrapper traceability-store; do
  pkg_dir="${ROOT_DIR}/packages/${pkg}"
  if [ -f "${pkg_dir}/pyproject.toml" ] && [ -n "${PYTHON_CMD}" ]; then
    info "Installing ${pkg} Python dependencies..."
    if [ ! -d "${pkg_dir}/.venv" ]; then
      ${PYTHON_CMD} -m venv "${pkg_dir}/.venv"
    fi
    "${pkg_dir}/.venv/bin/pip" install -q -e "${pkg_dir}[dev]" 2>/dev/null \
      || "${pkg_dir}/.venv/bin/pip" install -q -e "${pkg_dir}" 2>/dev/null \
      || warn "Could not install ${pkg} deps — may require the package to be implemented first"
    success "${pkg} dependencies installed"
  else
    info "Skipping ${pkg} Python install (pyproject.toml not found or python not available)"
  fi
done

echo ""

# ─── 4. Build Docker images ───────────────────────────────────────────────────
info "Building Docker images (this may take a few minutes)..."
${COMPOSE_CMD} -f "${ROOT_DIR}/docker-compose.yml" build --parallel
success "Docker images built"
echo ""

# ─── 5. Start the stack ───────────────────────────────────────────────────────
info "Starting SignalOps stack..."
${COMPOSE_CMD} -f "${ROOT_DIR}/docker-compose.yml" up -d
success "Stack started"
echo ""

# ─── 6. Wait for postgres to be healthy ───────────────────────────────────────
info "Waiting for PostgreSQL to be ready..."
MAX_WAIT=60
ELAPSED=0
until ${COMPOSE_CMD} -f "${ROOT_DIR}/docker-compose.yml" exec -T postgres \
    pg_isready -U "${POSTGRES_USER:-signalops}" -d "${POSTGRES_DB:-signalops}" &>/dev/null; do
  if [ "${ELAPSED}" -ge "${MAX_WAIT}" ]; then
    error "PostgreSQL did not become ready within ${MAX_WAIT} seconds."
  fi
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done
success "PostgreSQL is ready"
echo ""

# ─── 7. Run database migrations ───────────────────────────────────────────────
info "Running Alembic database migrations..."
${COMPOSE_CMD} -f "${ROOT_DIR}/docker-compose.yml" exec -T traceability-store \
  alembic upgrade head \
  && success "Migrations applied" \
  || warn "Migration failed — traceability-store may not be implemented yet. Skipping."
echo ""

# ─── 8. Seed sample data ──────────────────────────────────────────────────────
info "Seeding traceability store with sample data..."
bash "${SCRIPT_DIR}/seed.sh" \
  && success "Sample data seeded" \
  || warn "Seed failed — continuing (stack is still running)"
echo ""

# ─── 9. Wait for all services to be healthy ───────────────────────────────────
info "Waiting for all services to be healthy..."

wait_for_service() {
  local service="$1"
  local url="$2"
  local max_wait=60
  local elapsed=0
  until curl -sf "${url}" &>/dev/null; do
    if [ "${elapsed}" -ge "${max_wait}" ]; then
      warn "${service} did not become healthy within ${max_wait}s — it may not be implemented yet"
      return 0
    fi
    sleep 3
    elapsed=$((elapsed + 3))
  done
  success "${service} is healthy"
}

wait_for_service "traceability-store" "http://localhost:8002/health"
wait_for_service "mcp-wrapper"        "http://localhost:8001/health"
wait_for_service "agent-orchestrator" "http://localhost:8000/health"
wait_for_service "web-app"            "http://localhost:3000"
echo ""

# ─── 10. Print service URLs ───────────────────────────────────────────────────
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  SignalOps is running!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  Web App:              ${BLUE}http://localhost:3000${NC}"
echo -e "  Agent Orchestrator:   ${BLUE}http://localhost:8000${NC}"
echo -e "    POST /digest        ${BLUE}http://localhost:8000/digest${NC}"
echo -e "    GET  /health        ${BLUE}http://localhost:8000/health${NC}"
echo -e "  MCP Wrapper:          ${BLUE}http://localhost:8001${NC}"
echo -e "    GET  /health        ${BLUE}http://localhost:8001/health${NC}"
echo -e "  Traceability Store:   ${BLUE}http://localhost:8002${NC}"
echo -e "    GET  /health        ${BLUE}http://localhost:8002/health${NC}"
echo -e "    GET  /api/reports   ${BLUE}http://localhost:8002/api/reports${NC}"
echo -e "  PostgreSQL:           ${BLUE}localhost:5432${NC} (user: signalops, db: signalops)"
echo ""
echo -e "  To stop:   ${YELLOW}docker compose down${NC}"
echo -e "  To reset:  ${YELLOW}docker compose down -v${NC}  (removes pgdata volume)"
echo -e "  Logs:      ${YELLOW}docker compose logs -f [service-name]${NC}"
echo ""
