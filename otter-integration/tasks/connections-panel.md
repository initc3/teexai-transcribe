# Connections panel + optionally-multi-user

Branch: `connections-panel` (worktree). Goal: turn the single-owner / single-Otter-cookie app
into an **optionally multi-user** instance fronted by a **Connections panel** that shows each
user's login state for several *mechanisms* and onboards the disconnected ones.

Mechanisms:
- **Otter** (cookie) — per-user. Logged-out → onboarding: capture script **and** an "Otter Pilot"
  MV3 extension that copies otter.ai `sessionid`+`csrftoken` to a local `/onboard/otter`.
- **Google** (Calendar + Gemini notes) — per-user OAuth. Calendar = current/next meeting; Gemini
  notes = pull "Notes by Gemini" Docs from Drive as an alternate transcript/insight source.
- **Vexa** — owner-only. Owner self-hosts Vexa in the TEE as an alternate transcript source
  (`transcript.segment` shape is already source-agnostic per `cue/README.md`). Other users see it
  as "owner-hosted, not available to your account."

## Identity model (minimal multi-user)
- Owner = holds `OWNER_TOKEN` (unchanged; `#owner=` link).
- Other visitor = minted random `user token` on first connect, stored in localStorage
  (`otter_user_token`), sent as `X-User-Token`. Server uid = `owner` if owner token, else
  `sha256(user_token)[:12]`.
- Per-user store: `/data/users/<uid>/connections.json` = `{otter:{sessionid,csrftoken,identity},
  google:{token,identity}, source:"otter"|"vexa"}`. Prototype: stored plaintext on the /data
  volume (TEE-sealed at the volume level) — note, not field-encrypted yet.
- Errors propagate (no fallbacks). Owner-only mechanisms reject non-owner with 401/403.

## Phases (recommended order)

### P1 — Connections model + panel  ← centerpiece  [DONE, pending live owner/browser check]
- [x] `connections.py`: registry (otter/google/vexa); `otter_status` resolves `/user`; `google_status`
      checks stored token; `vexa_status` owner-only + `VEXA_URL`. Probe converts logged-out → connected:
      false with real error text in `error` (not masked).
- [x] `users.py`: load/save `DATA/users/<uid>/connections.json`; `uid_for` (owner|hashed|None).
- [x] `otter_session.open_session(cookies=None)` — None=env/chrome (unchanged), explicit cookies =
      validate a per-user login. Captures `s.user` for identity.
- [x] server: `GET /connections` (per-user statuses; before owner gate) + `POST /onboard/otter`
      (any identified user; validates via `/user` then stores; before owner gate). `DATA = users.DATA`.
- [x] `index.html`: per-visitor user token (localStorage, `X-User-Token`); Connections panel in intro —
      card per mechanism, status dot + identity, connect CTA expands onboarding.
- Verified: compile; uid_for + store round-trip; `/connections` anon→empty, user→3 mechanisms (otter
      false / google false / vexa locked); `/onboard/otter` no-identity→401, bad cookie→graceful error.
- [x] E2E (Playwright/Chromium, `otter_web/e2e_connections.py`, 11/11): mock Otter API + real server.
      guest panel states → onboarding expands → onboard POST flips Otter to connected → owner sees Otter
      + Vexa connected. Report + screenshots: `tasks/connections-e2e-report.md`, `tasks/e2e/*.png`.
      Test seam: `OTTER_API_BASE` env override on `otter_session.BASE` + `server.OTTER`.
- [ ] LIVE check (owner): owner with a real Chrome otter.ai cookie shows Otter connected w/ real email
      (E2E proves the wiring against a mock; this is the only-real-cookie confirmation).

### P2 — Otter onboarding (script + Otter Pilot extension)  [DONE, pending live browser load]
- [x] `onboard_otter.py`: reads Chrome otter.ai cookie via `browser_cookie3`, POSTs to the onboarding URL.
- [x] `extensions/otter-pilot/` MV3 (subagent): `manifest.json` (cookies+storage, otter.ai+http/https
      host perms), `popup.{html,js}` reads `sessionid`+`csrftoken` via `chrome.cookies.getAll` and POSTs
      `{sessionid,csrftoken}` to the pasted URL; shows identity / real error. README + load steps.
- [ ] LIVE check: side-load in Chrome, paste a user's onboarding URL, confirm panel flips to connected.

### P3 — Google app
- [x] Calendar (DONE): `google_app.py` — hand-rolled OAuth over `requests` (no google libs).
      `/google/auth`→consent (state=token), `/google/callback`→token exchange + userinfo, stored per
      user; `/calendar` lists next-24h events; token auto-refresh. Panel: connect→OAuth, connected card
      shows email + next meetings (📅 time · title · join). External URLs env-overridable (test seam).
      Config: `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI`.
- [x] Owner token-file reuse: `GOOGLE_TOKEN_FILE` points at an existing authorized-user json (the
      standalone calendar tool's `calendar_token.json`); app reads + refreshes it in place (read-only,
      no copy, no re-consent). Identity = primary calendar id (only calendar.readonly needed). Setup: `docs/google-setup.md`.
- [x] E2E (Playwright, `otter_web/e2e_google.py`, 5/5): mocks consent→token→primary→events; covers the
      per-user OAuth redirect chain AND the owner token-file path. Report: `tasks/google-e2e-report.html`.
- [x] LIVE check DONE: ran against the real work `calendar_token.json` → Google connected as
      socrates1024@gmail.com, `/calendar` returned a real event, panel rendered it. Otter intentionally
      errored (dead port) to confirm errors surface, not masked.
- [x] Gemini notes (DONE): events carrying a "Notes by Gemini" attachment → Drive export to text →
      ingested through the SAME decode pipeline as Otter (`ingest_gemini`, otid `gem_<fileId>`, source=
      gemini). `GET /gemini` lists, `POST /gemini/import` ingests; panel: "scan Gemini notes" in the
      Google card → per-note import → shows up in conversations. Reuses the existing drive.readonly scope.
- [x] E2E (in `e2e_google.py`, now 8/8): mocks the Notes-by-Gemini attachment + Drive export + NEAR
      decode (`NEAR_URL` env seam); scan→import→decode→appears as a conversation. Report screenshots updated.
- [x] LIVE check DONE: scanned 13 real Notes-by-Gemini meetings from the work token; imported a real Doc
      ("hermes office hours") → 391 segments → 198 decoded nodes (7 topics, 2 decisions, 6 action items).
      NEAR key sourced from `~/projects/ic3camp-teexai/.env` (per deploy_cvm.sh) — not re-entered.
      404s on other-attendees' notes surfaced honestly. Imported data stays in the gitignored data dir.

### P4 — Vexa mode (source swap)
- [ ] `sources.py`: `live_segments(uid)` abstraction; `OtterSource` (current logic) + `VexaSource`
      (poll owner's TEE Vexa for the active meeting, map to `{order,uuid,speaker,text}`).
- [ ] Per-user active source toggle in the panel (owner-only for Vexa). Live/graph polls read the
      user's selected source.
- [ ] `VEXA_URL` / `VEXA_API_KEY` env; status check; deploy note for self-hosting Vexa in the CVM.

### P5 — Multi-user isolation (deepen; may defer)
- [ ] Per-user data dirs for STATE/LIVE so two users' meetings don't collide. (Today STATE_DIR is
      global; owner-only until this lands.)

## Verify
- [ ] Server boots; `/connections` returns correct statuses for owner (Otter connected via chrome)
      and a fresh anon user (all disconnected).
- [ ] Otter Pilot extension side-loads in Chrome, copies cookie, `/onboard/otter` validates + panel
      flips to connected.
- [ ] Google OAuth round-trips; calendar event + a Gemini note render.
- [ ] Vexa: owner sees toggle; anon user sees owner-only locked state. Source swap drives the same
      decode pipeline.
- [ ] No fallbacks: a 401 Otter cookie surfaces as disconnected w/ onboarding, not a masked error.
