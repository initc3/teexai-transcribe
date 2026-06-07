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
asr/          local whisper, WS: PCM in -> transcript out  (hermetic; no near.ai key needed)
test-runner/  collects transcripts, asserts listener-pass + eavesdropper-fail
audio/        injected WAV fixture (44.1kHz/stereo/16-bit)
```

ASR note: kept hermetic (local whisper) so the test needs no key/network. Pointing the
listener at teexai-transcribe's `/api/transcribe` (near.ai TEE path) instead is a config
swap for the "real" integration.

## Run (target)

```bash
cd jitsi && cp .env.sample .env && ./gen-passwords.sh && cd ..
docker compose up --build --abort-on-container-exit --exit-code-from test-runner
```

## Status

- [x] M1 — Jitsi stack up, self-signed HTTPS, serves config.js + lib-jitsi-meet.min.js;
      jicofo+jvb healthy; JVB advertises its in-network IP (in-container media OK).
- [ ] M2 — pseudo-headed Chromium bot joins a room via lib-jitsi-meet.
- [ ] M3 — publisher injects WAV; listener taps PCM -> whisper transcript (no E2EE yet).
- [ ] M4 — shared-key E2EE on; eavesdropper (no key) gets garbage.
- [ ] M5 — single-command one-shot with pass/fail exit code.

## Notes

- `jitsi/.env` (passwords) and `jitsi/config/` (runtime) are gitignored.
- Bring the stack down: `cd jitsi && docker compose down`.
