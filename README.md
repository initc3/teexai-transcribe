# teexai-transcribe

A small FastAPI app that proxies [near.ai](https://cloud-api.near.ai) for audio
transcription, chat, and a tool-using agent, packaged to run inside a
[Phala](https://cloud.phala.com) Confidential VM (TDX). The `NEAR_API_KEY` is
supplied to the CVM as a sealed environment variable — it is never baked into
the image.

## Endpoints

- `GET  /` — static demo UI (`static/index.html`)
- `POST /api/transcribe` — multipart `file=<audio>`; converted to 16 kHz mono Opus via `ffmpeg`, sent to `whisper-large-v3`
- `POST /api/chat` — `{messages, model?}` → chat completion
- `POST /api/agent` — `{messages, model?}` → tool-using loop (`get_current_time`, `save_note`, `list_notes`)

## Run locally

```bash
export NEAR_API_KEY=sk-...
uv venv && uv pip install -r requirements.txt   # or: pip install -r requirements.txt
./run.sh                                         # serves on 127.0.0.1:8000
```

Requires `ffmpeg` on the host.

## Build & push image

```bash
docker build -t ghcr.io/amiller/teexai-transcribe:latest .
docker push ghcr.io/amiller/teexai-transcribe:latest
```

The image must be pullable by the Phala node (public, or with pull credentials).

## Deploy to Phala CVM

```bash
phala deploy -n teexai-transcribe -c docker-compose.yml -e NEAR_API_KEY="$NEAR_API_KEY" --wait
```

Redeploy after pushing a new image:

```bash
phala deploy --cvm-id <CVM_ID> -c docker-compose.yml
```

`docker-compose.yml` references the published image and reads `NEAR_API_KEY`
from the sealed env injected by Phala.

## Notes

- `.env`, `service-account.json`, and any `*.json` are gitignored — do not commit secrets.
- The `Dockerfile` copies only `app.py`, `requirements.txt`, and `static/`, so nothing else in the working tree ends up in the image.
