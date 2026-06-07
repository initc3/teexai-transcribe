#!/bin/bash
# Self-contained E2EE integration test. Brings the whole stack up, runs the
# assertion, and ALWAYS tears it down. Exit code == test verdict (0 = PASS).
set -uo pipefail
cd "$(dirname "$0")"
ENVFILE=jitsi/.env

if [ ! -f "$ENVFILE" ]; then
  echo "[run] generating $ENVFILE"
  (cd jitsi && cp .env.sample .env && ./gen-passwords.sh)
fi

# ASR transcribes via near.ai (no local whisper). Load the key from the repo .env.
if [ -z "${NEAR_API_KEY:-}" ] && [ -f ../.env ]; then
  set -a; . ../.env; set +a
fi
: "${NEAR_API_KEY:?NEAR_API_KEY not set (expected in ../.env)}"
export NEAR_API_KEY

cleanup() { docker compose --env-file "$ENVFILE" down >/dev/null 2>&1; }
trap cleanup EXIT

docker compose --env-file "$ENVFILE" build
docker compose --env-file "$ENVFILE" up --abort-on-container-exit --exit-code-from test-runner
code=$?
echo "[run] test exit code: $code"
exit $code
