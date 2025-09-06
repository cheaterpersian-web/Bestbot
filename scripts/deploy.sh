#!/usr/bin/env bash
set -euo pipefail

if [ ! -f .env ]; then
  echo "[deploy] .env not found. Copying from .env.example"
  cp .env.example .env
  echo "[deploy] Please edit .env and set DOMAIN, EMAIL, BOT_TOKEN, WEBAPP_URL."
  exit 1
fi

echo "[deploy] Bringing up stack with HTTPS (Caddy) ..."
docker compose up -d --build db api bot caddy

echo "[deploy] Waiting for API health..."
for i in {1..30}; do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    echo "[deploy] API is healthy"
    break
  fi
  sleep 2
done

echo "[deploy] Done. Ensure your DNS A/AAAA records point to this server for DOMAIN in .env."

