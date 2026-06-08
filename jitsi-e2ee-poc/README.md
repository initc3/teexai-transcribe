# jitsi-e2ee-poc

One-shot docker-compose that proves: **with E2EE on, only a participant holding the key can
process the audio — the server can't.** Self-hosted Jitsi + pseudo-headed Chromium bots
(publisher / listener / eavesdropper) + a Whisper ASR. Design + grounded mechanics:
[../agentic-meeting-skill/jitsi-e2ee-docker-poc.md](../agentic-meeting-skill/jitsi-e2ee-docker-poc.md).

## The assertion

Same E2EE media reaches every participant:
- `listener` (correct shared key) -> transcript ~= injected text  -> PASS
- `eavesdropper` (no key) -> garbage (= what a server-side tap sees) -> PASS proves E2EE

## Layout

```
jitsi/        vendored jitsi/docker-jitsi-meet (stable-9646): web, prosody, jicofo, jvb
bots/         bot.html + join JS + AudioWorklet (served BY the web container, https origin)
asr/          thin shim: buffers PCM, forwards to near.ai whisper-large-v3 (no local model)
test-runner/  collects transcripts, asserts listener-pass + eavesdropper-fail
audio/        injected WAV fixture (44.1kHz/stereo/16-bit)
```

ASR note: transcription is offloaded to near.ai (whisper-large-v3, the same TEE path
`teexai-transcribe` uses) — no local whisper model, so it doesn't eat laptop RAM. The shim
just buffers decrypted PCM and POSTs a WAV. `run.sh` loads `NEAR_API_KEY` from `../.env`;
the test therefore needs that key + network egress (it is not hermetic).

## Run

```bash
./run.sh    # builds, runs the test, ALWAYS tears down; exit 0 = PASS
```

`run.sh` auto-generates `jitsi/.env` (passwords) on first run. The stack only exists for
the duration of the test — `--abort-on-container-exit` stops it when `test-runner` exits and
the `trap` removes the containers. Nothing is left running.

Example PASS:
```
[test] listener     samples=737920  overlap=0.83 text='...the quick brown fox jumps over the lazy dog...'
[test] eavesdropper samples=1232000 overlap=0.00 text=''
[test] RESULT: PASS — E2EE holds: only the keyed participant reads audio
```
The eavesdropper *receives* the frames (non-zero samples) but recovers no audio — exactly
what a server-side tap sees.

## Status — all green

- [x] M1 — Jitsi stack up, self-signed HTTPS, serves config.js + lib-jitsi-meet.min.js.
- [x] M2 — pseudo-headed Chromium bots join via lib-jitsi-meet (in-network wss, --ignore-cert).
- [x] M3 — publisher injects WAV; listener taps PCM via AudioWorklet -> near.ai whisper.
- [x] M4 — shared-key E2EE (externallyManagedKey); keyless eavesdropper gets garbage.
- [x] M5 — single-command self-cleaning one-shot with pass/fail exit code.

## Hard-won fixes

- E2EE crypto runs in a Web Worker — must vendor `lib-jitsi-meet.e2ee-worker.js` next to the
  main lib, served from the page origin, or decryption silently never engages.
- Startup race: bots must not join before jicofo joins the bridge brewery / discovers
  components, else `CONFERENCE_FAILED focusDisconnected`. Handled by a settle delay + a
  rejoin retry in bot.js (jicofo's `/about/health` is 404 in this build, so don't poll it).
- Page secure-context (needed for insertable streams) comes free via `http://localhost`
  inside each bot container; the cross-origin wss to `web` uses `--ignore-certificate-errors`.

## Notes

- `jitsi/.env` (passwords) and `jitsi/config/` (runtime) are gitignored.
- Bring the stack down: `cd jitsi && docker compose down`.
