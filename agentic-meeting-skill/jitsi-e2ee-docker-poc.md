# One-Shot E2EE Jitsi + Audio-Processing Docker POC

Date: 2026-06-06

Goal: a single `docker compose up` that stands up a self-hosted Jitsi stack with E2EE,
injects known audio, transcribes it at a keyed participant endpoint, and asserts that only
a participant holding the E2EE key can read the audio. Proves the property our whole design
depends on: E2EE holds against the server, but an attested participant can still process
audio (see [meet-bot-detection-vs-jitsi.md](./meet-bot-detection-vs-jitsi.md),
[jitsi-meeting-skill-research.md](./jitsi-meeting-skill-research.md) line 517).

## Key architectural fact

E2EE in Jitsi is purely client-side (WebRTC Insertable Streams + SFrame/AES-GCM). The SFU
never holds the key; there is no server E2EE config. So server-side taps (JVB, Jibri,
Jigasi) cannot read E2EE audio. The processor MUST be a participant that holds the key and
decrypts at the endpoint. That is the design, not a workaround — and it is what makes the
TEE-ASR story coherent: plaintext audio only ever exists inside the keyed (attested) bot.

## Browser strategy: pseudo-headed, not headless

Bots run a real Chromium/Brave under a virtual display (Xvfb) in each container, driven by a
custom extension — "pseudo-headed." This sidesteps the only unconfirmed risk (whether
`--headless=new` supports insertable-streams E2EE); a headful browser supports it normally,
plus autoplay, fake-audio, and Web Audio behave as in a real browser.

## Confirmed mechanics (lib-jitsi-meet master, fetched 2026-06-06)

### Shared-key E2EE (no Olm) — deterministic for tests
```js
// config:
config.e2ee = { externallyManagedKey: true };   // -> ExternallyManagedKeyHandler, sharedKey:true, no Olm
// in each bot, after joining:
const encryptionKey = await crypto.subtle.importKey(
  'raw', RAW_KEY_BYTES /* same 16 bytes in every bot */, 'AES-GCM', false, ['encrypt','decrypt']);
conference.toggleE2EE(true);
conference.setMediaEncryptionKey({ encryptionKey, index: 0 });
```
- API on `JitsiConference`: `toggleE2EE(enabled)`, `setMediaEncryptionKey({encryptionKey,index})`,
  `isE2EEEnabled()`, `isE2EESupported()`.
- Cipher: AES-GCM 128-bit. `enableInsertableStreams` is set automatically when E2EE is on.
- Reference flow: jitsi-meet `react/features/e2ee/middleware.ts` (importKey -> toggle -> setKey).

### Secure context
Insertable streams + transferable streams + Web Workers require HTTPS or `localhost`. Serve
the Jitsi web container over self-signed TLS; bots launch with `--ignore-certificate-errors`.
No E2EE env var exists in `docker-jitsi-meet/env.example` (confirmed) — TLS is the only
server-side dependency.

### Publisher: inject a known WAV as the mic
Chrome flags: `--use-fake-device-for-media-stream --use-fake-ui-for-media-stream
--use-file-for-fake-audio-capture=/audio/sample.wav`. WAV must be 44.1 kHz / stereo /
16-bit PCM (`ffmpeg -ar 44100 -ac 2 -sample_fmt s16`). File does NOT loop — make it long
enough for the test.

### Listener: tap decrypted PCM
After E2EE decrypt the remote track is a normal `MediaStreamTrack`. Pipeline:
`AudioContext` -> `createMediaStreamSource(stream)` -> `AudioWorkletNode` -> PCM frames over
WebSocket to the ASR container. Gotchas (all confirmed):
- Attach the remote track to a muted, autoplay `<audio>` element too, or Web Audio yields
  silence.
- Launch with `--autoplay-policy=no-user-gesture-required` so the AudioContext is `running`.
- Wire up only after the track is added / connection established (silent until DTLS connects).

## Container topology

```
jitsi-web (TLS) / prosody / jicofo / jvb      # official jitsi/docker-jitsi-meet, 4 services
bot-publisher    # Xvfb + Chromium, fake-audio WAV, joins room, sets shared E2EE key
bot-listener     # Xvfb + Chromium + extension, shared key, decrypts, PCM -> WS -> asr
bot-eavesdropper # Xvfb + Chromium, joins WITHOUT key (or wrong key)  -> garbage audio
asr              # teexai-transcribe whisper, WS endpoint: PCM in -> transcript out
test-runner      # waits for transcripts, asserts, exits 0/1
```

## The E2EE assertion (fully self-contained)

Same media on the wire to every participant:
- bot-listener (correct key) transcript ~= expected text  -> PASS
- bot-eavesdropper (no/wrong key) transcript = garbage     -> PASS (proves E2EE)

The eavesdropper is exactly what a server-side tap would see, so this demonstrates the
server cannot read the audio without standing up Jibri.

## Build checklist

- [ ] Vendor `jitsi/docker-jitsi-meet` compose + `.env` (gen-passwords), enable self-signed TLS.
- [ ] Base bot image: Xvfb + Chromium/Brave + a minimal join page importing lib-jitsi-meet
      (served by jitsi-web at `/libs/lib-jitsi-meet.min.js`) + driving extension.
- [ ] Publisher bot: fake-audio flags + WAV fixture; join + shared key + publish.
- [ ] Listener bot: shared key + AudioWorklet PCM tap -> WS client.
- [ ] Eavesdropper bot: same as listener, key omitted/wrong.
- [ ] ASR: WS endpoint on teexai-transcribe (PCM frames -> running whisper -> transcript).
- [ ] test-runner: collect both transcripts, fuzzy-match expected, assert listener-pass +
      eavesdropper-fail, exit code.
- [ ] `docker compose up --abort-on-container-exit --exit-code-from test-runner`.

## Open questions to settle before building

- Bot control surface: custom extension vs. a hosted bot page the browser navigates to
  (user prefers extension-driven containers).
- ASR interface: teexai-transcribe currently is FastAPI HTTP; needs a small streaming-PCM
  WS shim (verify app.py interface).
- Reuse vs. fresh: build bots from the existing teexai-transcribe image, or a separate
  bot image that talks to it over the network.

## Sources

- lib-jitsi-meet `JitsiConference.ts`, `modules/e2ee/E2EEncryption.js`, `ExternallyManagedKeyHandler.js`, `doc/e2ee.md`
- jitsi-meet `react/features/e2ee/middleware.ts`
- jitsi/docker-jitsi-meet `env.example`
- Chromium fake-audio: `media/audio/fake_audio_input_stream.h`
- Web Audio + remote track gotcha: Chromium issue 40184923, Mozilla bug 1283549
