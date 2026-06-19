# lessons / integration notes

This session is the **integrator** — it folds the feature work other sessions land in this
folder into a working app. Notes the integrator should carry forward:

## Matrix
- **A bot post only "counts" if a human can SEE it** — an `event_id`/200 means the server
  accepted the event, NOT that anyone can read it. Always invite the intended human to the
  room you post to and verify membership. (Burned 2026-06-19: bot posted 16 msgs to an
  unencrypted room Andrew was never invited to → "nothing posted".) Fixed in skill PR
  teleport-computer/shape-rotator-matrix#48.
- `mtrx.shaperotator.xyz` default rooms (space/children/DMs) are **E2EE**; a plain-HTTP
  `m.notice` client cannot post to them. The copilot now uses a `matrix-nio[e2e]` sidecar
  (`otter_web/matrix_sidecar.py`) posting to the encrypted DM. `matrix.py` enqueues to a
  /data spool; the sidecar drains it. Needs `MATRIX_DEVICE_ID` + libolm in the image.
- **Cross-sign blocker:** clearing Element's yellow "unverified by owner" shield needs the
  bot account's *password* (homeserver UIA on `/signup/api/crosssign`); only the access
  token was persisted. Either save the bot password, or run Paste C (mautrix SAS) for a
  green shield. Messages decrypt regardless.

## Live copilot
- Live meetings surface bugs replay can't: the whole backlog hits one decode call on a
  mid-meeting restart → `DECODE_MAX=10` caps segments/call so the model's JSON isn't
  truncated. Live diarization gives no speaker labels (`SNone`); names settle post-meeting.
- `otter_wake.py` is the headless auto-driver (polls `/graph`, idle 45s / live 6s) = the
  "it knows a meeting started" loop; run it alongside the server. It sends `X-Auth-Token=OWNER_TOKEN`
  because `/graph` is owner-gated.

## tee-daemon deploy
- Deployed to the running CVM `915c8197…-prod7.phala.network` as a **Layer-1 image** via
  `deploy_cvm.sh` (inline `manifest.env`, NOT `env_passthrough` — the daemon's own env never received
  the otter secrets). Admin token from `hermes-agent/deploy-notes/.env.staging`. Image
  `ghcr.io/amiller/teexai-otter` must be **public** for the CVM to pull. `--force` re-pulls latest.
- **gVisor DNS bug**: the CVM runs `runsc`, which breaks Docker's embedded resolver (127.0.0.11) →
  `NameResolutionError` on otter.ai/near.ai. Fix: the container CMD overwrites `/etc/resolv.conf`
  with `8.8.8.8`/`1.1.1.1` before launching. The container runs sidecar + otter_wake + server.
- Owner access: `<CVM>/otter/#owner=<OWNER_TOKEN>`. Secrets are inline in the manifest (visible in the
  deploy response) — single-player, sealed in the CVM volume.
