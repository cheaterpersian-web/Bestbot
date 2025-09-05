#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH=/app

echo "[boot] Effective DATABASE_URL: ${DATABASE_URL//:*@/:***@}"
if [ -n "${BOT_TOKEN:-}" ]; then
  echo "[boot] BOT_TOKEN present: ****${BOT_TOKEN: -4}"
else
  echo "[boot] BOT_TOKEN not set"
fi

echo "[boot] Running database migrations (if any)..."
if [ -d "/app/alembic" ]; then
  alembic upgrade head || echo "[boot] Alembic upgrade failed or no migrations. Falling back to create_all."
fi

echo "[boot] Ensuring database schema exists..."
python - <<'PY'
import asyncio
from core.db import init_db_schema
asyncio.run(init_db_schema())
PY

mode="${1:-}"
shift || true

if [ "$mode" = "api" ]; then
  exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers
elif [ "$mode" = "bot" ]; then
  exec python -m bot.main
else
  # Execute arbitrary command if provided
  exec "$@"
fi

