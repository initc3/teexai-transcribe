# otter-integration — agent guide

Read this first. It says exactly what each tool does, what it touches, what it writes,
and what it costs — so it is unmysterious what we do with your Otter account, whether
you run it on your laptop or hand it to a TEE pod to run for you.

Otter has **no public API** on Pro/lower tiers. Everything here reuses a logged-in
Otter session cookie against Otter's internal `https://otter.ai/forward/api/v1/`
endpoints. Read-only: we pull transcripts/frames/audio you already have access to. We
never write to your Otter account.

## Three run modes — one image, one diff

The same code runs three ways. The **only** thing that changes is where the Otter
session cookie comes from (`otter_session.py`) and how the secret is delivered:

| Mode | Session provider | Cookie source | Secrets |
|------|------------------|---------------|---------|
| **Local** | `OTTER_SESSION=chrome` | your Chrome otter.ai login (`browser_cookie3`) | NEAR key in your env |
| **Personal TEE pod** | `OTTER_SESSION=sealed` | `OTTER_SESSIONID`/`OTTER_CSRFTOKEN` you inject | sealed env (Phala) |
| **Hosted turnkey** | `OTTER_SESSION=sealed` | session cookie you delegate to the host | sealed env (Phala) |

A TEE pod has no browser, so it can't read your Chrome login — you hand it the two
cookies (`sessionid`, `csrftoken`) as **sealed secrets**, the same channel the root
service uses for `NEAR_API_KEY`. Everything downstream is byte-identical across modes.
That tiny diff (one module + how the secret arrives) is what keeps the hosted version
auditable: a reviewer reads `otter_session.py` and knows the pod can't do anything the
local run can't.

## Tools (verbs)

| File | Does | Touches | Writes | Cost |
|------|------|---------|--------|------|
| `otter_sync.py` | archive all transcripts (owned+shared) + frames + opt. audio | Otter API, `api.aisense.com` assets | `$OTTER_OUT` (default `../references/otter/`), `otter_state.json` | free |
| `otter_watch.py` | hold Otter's push socket open; wake on any activity (no polling) | `get_jwt_token` + `wss://ws.aisense.com` | stdout (frames) | free |
| `otter_live.py` | tail the in-progress meeting to stdout | Otter API (poll) | — | free |
| `otter_web/server.py` | live dashboard: transcript + slide + recap + conversation graph | Otter API + NEAR inference | per-meeting state in memory | NEAR tokens on recap/decode |
| `otter_web/replay.py` | drive the decode/graph path offline from a saved transcript | a transcript file (`--near` to hit NEAR) | optional graph JSON | free unless `--near` |
| `otter_web/mapview.py` | render a saved graph JSON → standalone HTML map | a graph JSON | an HTML file | free |
| `otter_capture.py` | document Otter's real web calls (HAR) — **local-only**, needs a browser | Otter web app (headless Chrome) | HAR + summary JSON | free |

`otter_capture.py` drives a real Playwright browser, so it does **not** run in a pod —
it's a local dev/observation tool. (Headless chromium is shown the login page; the tool
sends a normal UA + `--disable-blink-features=AutomationControlled` to look like a real
browser.) The pod runs `otter_web/server.py` or `otter_watch.py`.

### Push sockets (wake-on-activity) — observed live 2026-06-19

Auth for both: `GET forward/api/v1/get_jwt_token` (session cookies) → `{"token": "<JWT aud=ws-prod>"}`
(short-lived; re-mint on reconnect). Connecting **is** subscribing — no hello frame. Two channels:

- **`session_update?token=<jwt>&userid=<uid>`** — account-level. Headless client works
  (`otter_watch.py`). Silent when idle; pushes account events (e.g. `{"type":"feature_limit",
  "action":"update"}`). Use as the always-on presence/notify socket. (Whether it cleanly emits a
  "meeting went live" event is not yet confirmed — needs catching one at the moment of start.)
- **`speech_update?speech_id=<id>&token=<jwt>`** — the per-meeting feed: `presence` frames (who's
  viewing) and the live transcript. `speech_id` (≠ `otid`) is in the `speech` detail
  (`d["speech_id"]`). The browser receives these; a bare headless client handshakes (101) then gets
  dropped after one empty frame — Otter wants a browser-exact handshake (likely `permessage-deflate`
  / a subprotocol). **Unresolved.**

**Reliable transcript path today: REST `GET speech?otid=…`** — `transcripts[]` grows during a live
meeting (verified live). Poll it only while a meeting is live (~3–5s); the `speeches` list filtered
on `live_status=='live'` is the meeting-start detector. So: socket for presence/idle, REST for the
transcript, with `speech_update` push as a later optimization once the handshake is matched.

## What leaves the boundary

In TEE mode the audit question is "what data crosses the enclave wall?" — answer it the
way the root README does:

- The **Otter session cookie** stays sealed inside the pod; it is never logged or echoed.
- Transcripts/frames are pulled from Otter and written to the `/data` volume (on Phala an
  encrypted, enclave-bound persistent volume).
- For recap/decode, **transcript text and the current slide image** go to NEAR private
  inference (DeepSeek text, Gemini vision) — the same NEAR TEE the root service uses.
  Nothing else leaves.

## Auditing the hosted pod

The hosted turnkey instance publishes a TDX attestation whose **measurement pins the
container image**. The image builds reproducibly from this repo (`Dockerfile`). So
"audit the turnkey one by reference to the one here" is concrete: rebuild the image from
this source, compare the measurement to the quote. The capability table above is the
human-readable half of that claim; the attestation is the cryptographic half.

## Quickstart (local)

```bash
pip install -r requirements.txt          # + playwright only if you use otter_capture
export NEAR_API_KEY=sk-...                # for the web app's recap/decode
# stay logged into otter.ai in Chrome
python3 otter_sync.py --no-frames         # pull transcripts
python3 otter_web/server.py               # http://localhost:8137
```

## Build & deploy (pod) — mirrors ../README.md

```bash
docker build -t ghcr.io/amiller/teexai-otter:latest .
docker push ghcr.io/amiller/teexai-otter:latest
phala deploy -n teexai-otter -c docker-compose.yml \
  -e OTTER_SESSION=sealed -e OTTER_SESSIONID=... -e OTTER_CSRFTOKEN=... -e NEAR_API_KEY=$NEAR_API_KEY --wait
```

## Status / coming soon

- Now: local + pod images share `otter_session.py`; sealed-mode cookie session not yet
  smoke-tested end-to-end against the live Otter API.
- Soon: hosted turnkey instance + a `verify` step that checks the published measurement
  against a rebuild of this repo.
- Electron wrapper over `otter_web/server.py` for a desktop "personal app" is a thin
  webview shell — not built yet.
