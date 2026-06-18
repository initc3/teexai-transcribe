#!/usr/bin/env bash
# Create user+token via admin API, then request a bot into the Meet.
set -euo pipefail
GW=${GW:-http://localhost:8056}
ADMIN=${ADMIN_TOKEN:-devadmintoken123}
MEET=${MEET:-uxu-hkbq-kyh}

echo "1) create user"
UID_=$(curl -s -X POST "$GW/admin/users" -H "X-Admin-API-Key: $ADMIN" \
  -H "Content-Type: application/json" \
  -d '{"email":"andrew@teleport.computer","name":"Andrew","max_concurrent_bots":2}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "   user id=$UID_"

echo "2) create bot token"
TOKEN=$(curl -s -X POST "$GW/admin/users/$UID_/tokens?scope=bot" -H "X-Admin-API-Key: $ADMIN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
echo "   token=$TOKEN"

echo "3) request bot into google_meet/$MEET"
curl -s -X POST "$GW/bots" -H "X-API-Key: $TOKEN" -H "Content-Type: application/json" \
  -d "{\"platform\":\"google_meet\",\"native_meeting_id\":\"$MEET\"}" | python3 -m json.tool

echo "$TOKEN" > /tmp/vexa-token.txt
echo "   token saved to /tmp/vexa-token.txt (for WS streaming)"
