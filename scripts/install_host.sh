#!/usr/bin/env bash
set -euo pipefail

# One-shot installer for VPS host (Docker-based, MySQL stack)

if ! command -v docker >/dev/null 2>&1; then
  echo "[install] Docker is required. Please install Docker first: https://docs.docker.com/engine/install/" >&2
  exit 1
fi

if ! command -v docker compose >/dev/null 2>&1; then
  echo "[install] Docker Compose Plugin is required. Follow: https://docs.docker.com/compose/install/linux/" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$ROOT_DIR"

echo "[install] Running interactive setup to generate .env"
bash scripts/setup.sh

echo "[install] Building and starting services"
docker compose up -d --build

echo "[install] Waiting for MySQL to be healthy"
timeout 60 bash -c 'until docker compose exec -T db sh -lc "mysqladmin ping -h localhost -u${MYSQL_USER:-vpn_user} -p${MYSQL_PASSWORD:-vpn_pass}"; do sleep 2; done'

echo "[install] Applying database migrations"
docker compose exec -T api alembic upgrade head || true

echo "[install] Installation complete. Tail bot logs with: docker compose logs -f bot"

