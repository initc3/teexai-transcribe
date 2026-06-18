# otter-integration

Piggybacks a logged-in Otter.ai session to pull transcripts + screenshare frames and serve a
live "what were we talking about?" recap. Otter has **no public API** on Pro/lower tiers, so
everything reuses the Chrome cookie you're already logged in with (`browser_cookie3`) against
Otter's internal `https://otter.ai/forward/api/v1/` endpoints. Google-SSO account → password
login is dead; cookie reuse is the only path. Stay logged into otter.ai in Chrome.

Sits alongside `../vexa-near-rig` (the bot-joins-the-meeting + NEAR-TEE transcription rig) as
the API-less, read-only complement: where Vexa rebuilds capture from open parts, this leverages
the high-quality transcript Otter already produces.

## Files

- **`otter_sync.py`** — archive puller. Transcripts (owned + shared, via `bulk_export` → diarized
  txt) plus screenshare frames (`get_speech` `images[]`). Incremental/resumable via
  `otter_state.json`; paced + backoff. Flags: `--no-frames`, `--audio`, `--max N`, `--force`.
- **`otter_live.py`** — terminal live tail of the in-progress meeting (`live_status=='live'`).
- **`otter_capture.py`** — Playwright HAR instrumentation (cookie-injected headless) to study
  the real web-app calls.
- **`otter_web/{server.py,index.html}`** — `localhost:8137` web app: live transcript + recap
  button + slide panel. Recap/vision via NEAR private inference (DeepSeek text, Gemini vision);
  `/frame` proxies cookie-auth PNGs.

## Endpoints (verified live)

- `GET user` → `userid`
- `GET speeches?userid&page_size&source=owned|shared` → list (`page_size=1000` is slow/throttle-prone)
- `POST bulk_export` (`x-csrftoken`, `{formats:txt, speech_otid_list:[otid]}`) → diarized txt; works owned **and** shared
- `GET speech?userid&otid` → detail incl `transcripts[]` + `images[]`
- Frames/audio live on `api.aisense.com` and need `sessionid`+`csrftoken` sent **explicitly** as
  cookies (cross-domain; the otter.ai jar won't send them).

## Gotchas

- Live diarization is weak (speaker labels are `None`/cluster ids); clean names settle
  post-meeting via `bulk_export`.
- Otter auto-screenshot is flaky (`CANNOTDETECTSHARE`); manual capture (`source:screenshot`)
  works, `auto_screenshot` often doesn't fire.
- Vision: `Qwen3-VL-30B` too slow (>60s) → use `gemini-2.5-flash`. Rate limits bite on bursts.

## Setup

```
pip install browser_cookie3 requests playwright   # playwright only for otter_capture
```

NEAR inference key for the web app is read from a local `.env.local` (not committed).

> `otter_sync.py` writes into `../references/otter/` relative to its own location. The canonical
> running instance lives in the `teleport/planning/scripts/` knowledge base; this copy is the
> versioned, shareable home for the code.
