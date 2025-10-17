#!/usr/bin/env bash
set -euo pipefail

# Reinstall (clean + rebuild + run) WITHOUT deleting the database volume
# Steps:
#  - Stop services (no -v)
#  - Clean local caches/__pycache__/*.pyc
#  - Rebuild images (no-cache) for api/bot
#  - Start stack
#  - Run Alembic migrations (non-destructive)

ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$ROOT_DIR"

# ---- Styling ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }

print_banner() {
  echo -e "${BLUE}────────────────────────────────────────────────────────${NC}"
  echo -e "${BLUE} Reinstall (keep DB) - VPN Telegram Bot ${NC}"
  echo -e "${BLUE}────────────────────────────────────────────────────────${NC}"
}

# ---- Checks ----
require_tool() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log_error "'$1' not found. Please install it first."
    exit 1
  fi
}

print_banner
require_tool docker
require_tool bash

if ! docker compose version >/dev/null 2>&1; then
  log_error "Docker Compose Plugin is required. See: https://docs.docker.com/compose/install/"
  exit 1
fi

if [ ! -f "docker-compose.yml" ]; then
  log_error "docker-compose.yml not found. Run this script from project root: $ROOT_DIR"
  exit 1
fi

# Flags
REBUILD_IMAGES=true
PULL_BASE=true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-rebuild)
      REBUILD_IMAGES=false
      shift ;;
    --no-pull)
      PULL_BASE=false
      shift ;;
    --help|-h)
      echo "Usage: $0 [--no-rebuild] [--no-pull]"
      exit 0 ;;
    *)
      log_warn "Unknown arg: $1"; shift ;;
  esac
done

# Ensure .env exists (do NOT recreate automatically to avoid overwriting)
if [ ! -f .env ]; then
  log_warn ".env not found. Running setup to create it."
  bash scripts/setup.sh
fi

log_info "Stopping services (preserving volumes, especially DB)..."
docker compose down || true

log_info "Cleaning caches (__pycache__, *.pyc)..."
find app -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
find app -type f -name '*.pyc' -delete 2>/dev/null || true

if [ "$PULL_BASE" = true ]; then
  log_info "Pulling base images (db/caddy, etc.)..."
  docker compose pull || true
fi

if [ "$REBUILD_IMAGES" = true ]; then
  log_info "Rebuilding images (api, bot) with --no-cache..."
  docker compose build --no-cache api bot
else
  log_info "Rebuilding images skipped (flag --no-rebuild)."
fi

log_info "Starting services..."
docker compose up -d
docker compose ps | cat

log_info "Waiting for DB to be ready (not recreating volumes)..."
timeout 60 bash -c 'until docker compose exec -T db sh -lc "mysqladmin ping -h localhost >/dev/null 2>&1"; do sleep 2; done' || true

log_info "Applying database migrations (non-destructive)..."
docker compose exec -T api alembic upgrade head || true

log_success "Stack is up. Tail bot logs with: docker compose logs -f bot | cat"
log_success "Health: curl -fsS http://localhost:8000/health || true"

