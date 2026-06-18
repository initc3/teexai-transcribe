#!/usr/bin/env bash
# Bring the Vexa+near rig back up and point a bot at MEET=<xxx-xxxx-xxx>.
set -euo pipefail
cd "$(dirname "$0")"
MEET=${MEET:?set MEET=abc-defg-hij}
VENV=~/projects/ic3camp-teexai/.venv/bin/python
set -a; . ~/projects/ic3camp-teexai/teexai-transcribe/.env; set +a   # NEAR_API_KEY

echo "1) postgres"
docker ps -q -f name=vexa-postgres | grep -q . || docker run -d --name vexa-postgres --network vexa-net \
  -e POSTGRES_DB=vexa -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
  postgres:17-alpine -c idle_in_transaction_session_timeout=60000 >/dev/null
until docker exec vexa-postgres pg_isready -U postgres -d vexa -q 2>/dev/null; do sleep 2; done

echo "2) vexa-lite"
docker ps -q -f name=vexa-lite | grep -q . || docker run -d --name vexa-lite --shm-size=2g --network vexa-net \
  -p 8056:8056 -p 8057:8057 -p 3000:3000 --add-host=host.docker.internal:host-gateway \
  -v vexa-lite-recordings:/var/lib/vexa/recordings \
  -e DATABASE_URL=postgresql://postgres:postgres@vexa-postgres:5432/vexa \
  -e DB_PASSWORD=postgres -e DB_SSL_MODE=disable -e REDIS_URL=redis://localhost:6379/0 \
  -e ADMIN_API_TOKEN=devadmintoken123 \
  -e VEXA_AUTH_COOKIE_NAME=vexa-token-lite -e VEXA_USER_INFO_COOKIE_NAME=vexa-user-info-lite \
  -e TRANSCRIPTION_SERVICE_URL=http://host.docker.internal:8001/v1/audio/transcriptions \
  -e TRANSCRIPTION_SERVICE_TOKEN=near vexaai/vexa-lite:latest >/dev/null
until curl -sf -o /dev/null http://localhost:8056/; do sleep 3; done

echo "3) near shim :8001"
ss -ltn | grep -q ':8001 ' || nohup $VENV -m uvicorn near-shim:app --host 0.0.0.0 --port 8001 >/tmp/near-shim.log 2>&1 & disown || true

echo "4) request bot -> $MEET"
MEET=$MEET bash join.sh

echo "5) recap+indicators :8088 (meeting=$MEET)"
sed -i "s/MEET = os.environ.get(\"MEET\", \"[a-z-]*\")/MEET = os.environ.get(\"MEET\", \"$MEET\")/" recap-service.py
ss -ltn | grep -q ':8088 ' && { p=$(ss -ltnp 2>/dev/null | grep ':8088 ' | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2); [ -n "$p" ] && kill "$p"; sleep 1; }
MEET=$MEET nohup $VENV -m uvicorn recap-service:app --host 127.0.0.1 --port 8088 >/tmp/recap.log 2>&1 & disown

echo "READY → http://127.0.0.1:8088   (admit the bot in the Meet)"
