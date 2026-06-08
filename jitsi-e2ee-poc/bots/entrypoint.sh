#!/bin/bash
set -e
ROLE=${ROLE:?need ROLE}
ROOM=${ROOM:-e2eeroom}
KEY=${EKEY:-}

echo "[$ROLE] waiting for jitsi web..."
until curl -ksf https://web/config.js >/dev/null; do sleep 1; done
echo "[$ROLE] settling (let prosody vhosts + jicofo brewery come up)..."
sleep 15  # residual connect/focus races are handled by retries in bot.js
for f in lib-jitsi-meet.min.js lib-jitsi-meet.e2ee-worker.js; do
  curl -ksf "https://web/libs/$f" -o "/srv/$f" \
    && echo "[$ROLE] fetched $f ($(wc -c <"/srv/$f") bytes)" \
    || echo "[$ROLE] MISSING $f"
done

EXTRA=""
if [ "$ROLE" = "publisher" ]; then
  TEXT=""
  for i in $(seq 1 8); do TEXT="$TEXT ${PHRASE}."; done
  espeak-ng -s 150 -w /srv/raw.wav "$TEXT"
  ffmpeg -y -i /srv/raw.wav -ar 44100 -ac 2 -sample_fmt s16 /srv/sample.wav 2>/dev/null
  echo "[$ROLE] generated sample.wav ($(wc -c </srv/sample.wav) bytes)"
  EXTRA="--use-fake-device-for-media-stream --use-fake-ui-for-media-stream --use-file-for-fake-audio-capture=/srv/sample.wav"
fi

python3 -m http.server 8080 --directory /srv >/dev/null 2>&1 &
Xvfb :99 -screen 0 1280x720x24 >/dev/null 2>&1 &
export DISPLAY=:99
sleep 1

URL="http://localhost:8080/bot.html?role=${ROLE}&room=${ROOM}&key=${KEY}"
echo "[$ROLE] launching chromium -> $URL"
exec chromium --no-sandbox --disable-dev-shm-usage --disable-gpu \
  --user-data-dir=/tmp/cr-${ROLE} --window-size=1280,720 \
  --no-first-run --no-default-browser-check --disable-extensions \
  --ignore-certificate-errors --autoplay-policy=no-user-gesture-required \
  $EXTRA "$URL"
