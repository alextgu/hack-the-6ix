#!/usr/bin/env bash
# Boot the FastAPI + Telegram webhook server.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; . ./.env; set +a; fi
if [ ! -d .venv ]; then ./scripts/setup.sh; fi
exec ./.venv/bin/uvicorn kamagachi.app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
