# todo: conversation decoder + topic graph + decision lens

Spec: `docs/decoder-graph-spec.md`. Brainstorm/triage: `docs/conversation-tooling-brainstorm.md`.
Decisions (2026-06-19): Otter-first input; build decoder + graph view + decision lens.

## Plan (verify before implementing)

- [x] Change 1: `/live` forwards `uuid` and `label` per segment (small passthrough)
- [x] Server state: `STATE[otid]` holding topics, nodes, decoded-uuids
- [x] Decoder: NEAR text-model call, JSON node output, batch trigger (>=4 new segs)
- [x] `/graph` endpoint returns `{topics, nodes, decisions}` (decisions = filtered view)
- [x] Client: cytoscape.js panel — compound nodes per topic, color by kind
- [x] Click topic cluster -> recap that cluster (reuse `/recap`)
- [x] Decisions rail (accreting list)
- [x] Replay harness (`otter_web/replay.py`): mocks Otter from a captured transcript, drives
      `graph_state()` in batches. Offline stub (deterministic, asserts) + `--near` real decoder.
- [ ] Probe (needs live meeting): live cluster-id (`label`) stability — replay uses named-speaker
      labels from the export, not live clusters, so this is still unverified live.

## Backlog (from co-processing sessions)

- [ ] **Redaction topics as a first-class node/capture.** During a meeting/processing, let Andrew
      flag a "redaction topic" — content that must NOT surface in any shared insight or report
      (e.g. naming/embarrassing specific competitors). The decoder should tag such segments and the
      report/recap generators must strip or generalize them before sharing. Surfaced 2026-06-19 while
      processing the dmarz call: the "jostle [competitors] into faster action" framing had to be
      redacted by hand from `teleport/planning/sessions/2026-06-19-dmarz-app-taps-report.html`.
      This is exactly the kind of note Andrew wants to capture *via* the transcription workflow itself.

## Three-mode TEE form factor (2026-06-19)

Goal: one image, three launch contexts (local / personal TEE pod / hosted turnkey),
one pluggable session module, one attestation tying the hosted pod back to this repo.

- [x] `AGENTS.md` — capability table, what's touched, what leaves the boundary, audit story
- [x] `otter_session.py` — shared session; `OTTER_SESSION=chrome|sealed` providers
- [x] sync/live/server route through `open_session()` (killed duplicated cookie code)
- [x] `server.py` NEAR key from env only (no `~/.env.local`); `HOST` env for container bind
- [x] `requirements.txt`, `Dockerfile`, `docker-compose.yml` mirroring the root Phala pattern
- [x] py_compile all touched files
- [x] local smoke: chrome-mode `open_session()` verified live (uid=24505923)
- [ ] pod smoke: sealed-cookie session against Otter API (needs deployed CVM)

## Push socket — wake on activity (2026-06-19)

Reverse-engineered Otter's live channel instead of polling. The web app holds one socket;
we hold the same one. Gentler than polling, near-instant.

- [x] `otter_capture.py`: record WS frames + realistic UA/anti-automation (headless was shown login)
- [x] Discovered handshake: `GET get_jwt_token` → JWT (aud=ws-prod), then
      `wss://ws.aisense.com/api/v2/client/session_update?token=&userid=`. Connecting = subscribing.
- [x] `otter_watch.py`: perpetual socket, token refresh on reconnect, errors propagate. Verified
      connects (1.8s) + holds idle. Added to Dockerfile.
- [ ] Observe a real activity frame (needs a live meeting) to learn the event shape
- [ ] Dispatch live-meeting frames → fire the decoder/recap (the wake-the-agent payoff)
- [ ] Speaker identity: map Otter cluster ids → people via in-enclave voiceprints (root service);
      confirm whether Otter exposes live audio or we compose with vexa-near-rig

## Demo: live copilot → Matrix, in tee-daemon (2026-06-19)

Goal this session: Andrew's own personal demo running in tee-daemon with real-time workflows
firing to Matrix. Builds on what's done above (sealed session, Dockerfile/compose, otter_watch).
Run location: tee-daemon **locally** via `docker compose up` (no cloud CVM token present this
session); same image/manifest later deploys to a real CVM + becomes the "run your own" template
([[tee-daemon-run-your-own]]). Deploy model verified: **Layer-1 image runtime** — `server.py` runs
as-is; secrets via `env_passthrough`; outbound HTTPS open (default `runc`, not gVisor — DNS bug).
smithers/cue: not now; cue fits the live loop later, smithers for bounded jobs ([[cue-smithers-for-live-loop]]).

- [ ] M0 inputs: Matrix homeserver + room id + bot/access token; confirm NEAR key source; pull Otter
      `sessionid`/`csrftoken` from Chrome for sealed env.
- [ ] M1 Prove existing app runs in tee-daemon: fix `requirements.txt` (add `websocket-client`); build
      image; bring up daemon (`docker compose up`); deploy as Layer-1 image project w/ `env_passthrough`
      for the 3 secrets; hit dashboard at `localhost:8080/<name>/`.
- [~] M2 Matrix-out + first workflow (vertical slice): `otter_web/matrix.py` (dry-run until creds set)
      + hook in `graph_state()` posting new `decision`/`action_item` nodes. Self-tested offline via
      replay on 3 recorded convos (dmarz/picreds fire, sri&tina silent). TODO: real Matrix creds for a
      live post; add an explicit good-point detector; richer message w/ source quote (needs `--near`).
- [ ] M3 Workflows: recap-for-joiners → Matrix; tag-to-summon (tag in transcript → Matrix invite ping);
      party-ball good-point celebration (dashboard-side).
- [ ] M4 (polish/stretch): one-button live HTML report → Matrix; wire `otter_watch.on_event` so a
      meeting going live auto-starts the decode/recap loop (the "it just knows" beat).

## Review

Implemented (2026-06-19):
- `server.py`: `/live` now forwards `uuid`+`speaker`; added `STATE`, `DECODE_SYS`, `decode()`,
  `graph_state()`, and `GET /graph`. Decoder uses NEAR text model with `response_format=json_object`,
  batches >=4 new segments, assigns/reuses topic ids server-side, marks uuids done.
- `index.html`: cytoscape via CDN; Feed/Graph tab toggle; compound topic clusters colored by kind;
  tap cluster -> `/recap` (text-only) for that thread; tap node -> show text; decisions rail in side
  panel; `pollGraph()` every 8s.

Verified locally: server imports + boots; `graph_state()` returns `{live:false}` against the live
Otter session (no crash, cookies read OK); graph-assembly unit test with a stubbed decoder produces
correct topics/nodes/decisions.

Not yet verified (requires a live meeting): real NEAR decode JSON shape end-to-end, cytoscape render,
cluster-recap click, and cluster-id stability over a real conversation. Errors propagate (no
fallbacks) — a malformed decode surfaces in the `/graph` error field like `/recap`.
