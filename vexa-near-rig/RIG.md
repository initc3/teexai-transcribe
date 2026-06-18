# Vexa + near confidential transcription rig

Practice rig: Vexa Lite joins a Google Meet, routes meeting audio to **near.ai's TEE
whisper-large-v3** instead of a local GPU, and serves a live transcript + recap.
Same Vexa package the cohort's **Conclave** team builds on.

## Architecture

```
Google Meet ── Vexa Lite bot (headless Chrome, child process)
                   │ POST /v1/audio/transcriptions (OpenAI shape, VAD-chunked)
                   ▼
            near-shim.py :8001 ──► cloud-api.near.ai  (whisper-large-v3, in TEE)
                   │ verbose_json segments
                   ▼
            Vexa gateway WS  tc:meeting:<id>:mutable
                   ▼
            recap-service.py :8088  ── live transcript + "what were we talking about" (near chat)
```

No GPU, no local inference. The only local compute is the browser bot; all ASR is in near's enclave.

## Pieces

| File | Role |
|---|---|
| `near-shim.py` (:8001) | OpenAI `/v1/audio/transcriptions` → near.ai. Also `/stats` for pipeline indicators. Bound `0.0.0.0` so the container reaches it via `host.docker.internal`. |
| `recap-service.py` (:8088) | Consumes Vexa gateway WS → rolling transcript; `/recap` summarizes recent talk via near chat; live pipeline panel (chunks, KB, latency sparkline). |
| `join.sh` | Create admin user + bot token, request a bot into a Meet. Token saved to `/tmp/vexa-token.txt`. |
| `.env` | `TRANSCRIPTION_SERVICE_URL` points Vexa at the shim; `ADMIN_TOKEN`. |
| `relaunch.sh` | Bring the whole stack back up and point at a new meeting. |

## Gotchas (learned the hard way)

- **IPv6:** this host has no IPv6 egress but DNS returns IPv6-only for Docker Hub → `docker pull` hangs at 0 bytes. Fix: `/etc/hosts` IPv4 pins for the registry hosts (needs sudo), or pull via `skopeo` (userspace IPv4) → `docker load`. The 7.3 GB Lite image was loaded via skopeo.
- **Ports:** host already uses 6379 (honcho redis) and 8080. Run Vexa Lite in **bridge mode** (not `--network host`) so those stay internal; only expose 8056/8057/3000.
- **near limits:** ~45 s / 2 MB per call — fine for VAD chunks.
- **Email validator** rejects `.local` / reserved TLDs for the admin user.

## Relaunch

```bash
MEET=abc-defg-hij bash relaunch.sh    # the xxx-xxxx-xxx from the Meet URL
```

Then open http://127.0.0.1:8088 and admit the bot in the Meet.

## To improve later

- **Chunk latency** (slightly slow): tune Vexa VAD in `services/vexa-bot/core/src/services/transcription-client.ts`
  (`max_speech_duration_s`, `min_silence_duration_ms`) for smaller/faster chunks; the :8088 sparkline shows the effect.
- **Captions triangulation:** Vexa scrapes native captions on **Teams** (free, can cross-check near). Google Meet has none in Vexa — audio→near is the only source unless a Meet caption scraper is added.
