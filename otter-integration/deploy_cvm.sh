#!/bin/bash
# Deploy otter copilot to Andrew's running tee-daemon CVM (hermes-staging) as a Layer-1 image.
# Secrets passed INLINE via manifest.env (the working mechanism used by matrix-greeter/feedling-web).
# env_passthrough is NOT usable here: it forwards from the DAEMON's own CVM env, which never
# received the otter secrets (would require a disruptive daemon redeploy).
set -euo pipefail

CVM="https://915c8197b20b831c52cf97a9fb7e2e104cdc6ae8-8080.dstack-pha-prod7.phala.network"
NAME="otter"
IMAGE="ghcr.io/amiller/teexai-otter:latest"
PORT=8137

DAEMON_TOKEN="$(grep '^TEE_DAEMON_TOKEN=' "$HOME/projects/hermes-agent/deploy-notes/.env.staging" | cut -d= -f2-)"

OTTER_ENV="$HOME/projects/ic3camp-teexai/teexai-transcribe/otter-integration/.env.local"
get_otter() { grep "^$1=" "$OTTER_ENV" | cut -d= -f2-; }
MATRIX_HOMESERVER="$(get_otter MATRIX_HOMESERVER)"
MATRIX_ROOM="$(get_otter MATRIX_ROOM)"
MATRIX_TOKEN="$(get_otter MATRIX_TOKEN)"
MATRIX_DEVICE_ID="$(get_otter MATRIX_DEVICE_ID)"
OWNER_TOKEN="$(get_otter OWNER_TOKEN)"
NEAR_API_KEY="$(grep '^NEAR_API_KEY=' "$HOME/projects/ic3camp-teexai/.env" | cut -d= -f2-)"

read -r OTTER_SESSIONID OTTER_CSRFTOKEN <<<"$(python3 -c "import browser_cookie3 as bc; j={c.name:c.value for c in bc.chrome(domain_name='otter.ai')}; print(j['sessionid'], j['csrftoken'])")"

export OTTER_SESSION=sealed HOST=0.0.0.0 OTTER_OUT=/data/otter
export BASE_URL="$CVM/$NAME"
export OTTER_SESSIONID OTTER_CSRFTOKEN NEAR_API_KEY \
       MATRIX_HOMESERVER MATRIX_ROOM MATRIX_TOKEN MATRIX_DEVICE_ID OWNER_TOKEN

ENV_JSON="$(python3 - <<'PY'
import json, os
keys = ["OTTER_SESSION","HOST","OTTER_OUT","BASE_URL",
        "OTTER_SESSIONID","OTTER_CSRFTOKEN","NEAR_API_KEY",
        "MATRIX_HOMESERVER","MATRIX_ROOM","MATRIX_TOKEN","MATRIX_DEVICE_ID","OWNER_TOKEN"]
print(json.dumps({k: os.environ[k] for k in keys}))
PY
)"

MANIFEST="$(python3 - <<PY
import json
env = json.loads('''$ENV_JSON''')
print(json.dumps({
  "name": "$NAME",
  "runtime": "image",
  "image": "$IMAGE",
  "image_port": $PORT,
  "volumes": [{"name": "otter-data", "mount": "/data"}],
  "env": env,
}))
PY
)"

echo "Deploying $NAME (image=$IMAGE port=$PORT) to $CVM ..."
[ "${1:-}" = "--force" ] && curl -sf -X DELETE -H "Authorization: Bearer $DAEMON_TOKEN" "$CVM/_api/projects/$NAME" >/dev/null 2>&1 && echo "(deleted existing)" || true

RESP="$(curl -s -X POST -H "Authorization: Bearer $DAEMON_TOKEN" \
  -H "Content-Type: application/json" -d "$MANIFEST" "$CVM/_api/projects")"
echo "Deploy response: $RESP"
