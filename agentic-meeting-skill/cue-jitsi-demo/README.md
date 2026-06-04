# Cue Jitsi Meeting Demo

This is the first concrete scaffold for the Jitsi/Hermes meeting skill:

```text
Jitsi meeting console
  -> teexai-transcribe transcript segments
  -> Cue observations
  -> conservative meeting actions or observe.pass
```

It does not yet join Jitsi or capture audio by itself. It proves the realtime decision layer: transcript segments enter Cue, and Cue emits structured meeting actions.

## Files

- `cue-meeting.config.mjs` — Cue server config with meeting-specific tools and a heuristic provider.
- `post-transcript-segment.mjs` — helper that posts one transcript segment to a Cue session.
- `fixtures/sample-observations.jsonl` — sample transcript observations for smoke testing.

## Run

Build Cue once if needed:

```bash
cd /home/amiller/projects/cue
pnpm build
```

Start the Cue meeting session server from this repo's config:

```bash
cd /home/amiller/projects/cue
node packages/server/dist/application/cue-server.cli.js \
  /home/amiller/projects/ic3camp-teexai/teexai-transcribe/agentic-meeting-skill/cue-jitsi-demo/cue-meeting.config.mjs
```

In another shell, subscribe to events:

```bash
python3 - <<'PY'
import asyncio, json, websockets

async def main():
    async with websockets.connect("ws://localhost:8798/sessions/demo/events") as ws:
        while True:
            print(await ws.recv())

asyncio.run(main())
PY
```

Post sample segments:

```bash
node /home/amiller/projects/ic3camp-teexai/teexai-transcribe/agentic-meeting-skill/cue-jitsi-demo/post-transcript-segment.mjs \
  "We decided Alice owns the follow-up by Friday." Andrew

node /home/amiller/projects/ic3camp-teexai/teexai-transcribe/agentic-meeting-skill/cue-jitsi-demo/post-transcript-segment.mjs \
  "Let's keep this off the record for now." Andrew
```

Or post the JSONL fixture:

```bash
while IFS= read -r line; do
  curl -sS -X POST http://localhost:8798/sessions/demo/observations \
    -H 'content-type: application/json' \
    -d "$line" | jq .
done < /home/amiller/projects/ic3camp-teexai/teexai-transcribe/agentic-meeting-skill/cue-jitsi-demo/fixtures/sample-observations.jsonl
```

## Current Actions

The config can emit:

- `meeting.decision_captured`
- `meeting.action_item_captured`
- `meeting.redaction_requested`
- `meeting.unverified_claim_flagged`
- `meeting.routing_requested`

Everything else should become `observe.pass`.

## Next Step

Connect `teexai-transcribe` to this by posting each final transcript segment as:

```json
{
  "type": "transcript.segment",
  "source": "teexai-transcribe",
  "payload": {
    "text": "We decided Alice owns the follow-up by Friday.",
    "speaker": "Andrew",
    "isFinal": true,
    "start": 12.4,
    "end": 17.2,
    "confidence": 0.91
  }
}
```

