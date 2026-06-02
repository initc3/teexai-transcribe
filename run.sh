#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] && set -a && . ./.env && set +a
export NEAR_API_KEY="${NEAR_API_KEY:?set NEAR_API_KEY or create .env}"
exec .venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
