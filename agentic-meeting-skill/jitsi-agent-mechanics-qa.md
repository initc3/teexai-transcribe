# Jitsi Agent Mechanics Q&A

Date: 2026-06-03

## Is Jitsi "Just WebRTC"?

No. Jitsi uses WebRTC for real-time media, but Jitsi Meet is a full conferencing system around WebRTC.

The media path is WebRTC:

- browsers capture mic/camera with WebRTC APIs;
- audio/video move over ICE + DTLS-SRTP;
- 1:1 calls can be peer-to-peer;
- group calls normally route through Jitsi Videobridge, an SFU.

But the meeting itself needs central services:

- the web app serves the client;
- Prosody/XMPP handles signaling, room membership, presence, chat, and roles;
- Jicofo coordinates the conference and bridge allocation;
- Jitsi Videobridge routes group media;
- Jibri handles server-side recording/streaming if configured;
- TURN/STUN help clients connect through NATs/firewalls.

So Jitsi is decentralized only in the limited sense that anyone can self-host it and room URLs can be created freely. A given meeting still depends on a Jitsi deployment such as `meet.jit.si` or `meet.example.com`.

## Is It Trivial For An Agent To Invite Me To A Jitsi Meeting?

Yes, if "invite" means create a link and send it.

A Jitsi meeting can be represented as a URL:

```text
https://meet.jit.si/some-random-room-name
```

or on a self-hosted deployment:

```text
https://meet.example.com/some-random-room-name
```

The agent can generate a high-entropy room name, create a calendar event, paste the URL into the location/description, and email/message the invite. That part is easy.

What is not trivial:

- making sure only invited people can join;
- making sure the agent is moderator/host;
- preventing guests from entering before the host;
- starting recording/transcription;
- retrieving transcript/recording artifacts afterward;
- guaranteeing behavior on public `meet.jit.si`.

For those, the agent likely needs either a self-hosted Jitsi deployment with secure-domain/JWT configuration or a supported managed service.

## What Would Let The Agent Respond Appropriately During The Meeting?

There are levels.

### Level 1: Meeting Coordinator

The agent does not listen live. It schedules the meeting, prepares agenda/context, creates the Jitsi link, and collects post-meeting artifacts if recording/transcription exists.

This is easy and useful.

### Level 2: Iframe Event Observer

The agent runs or controls a browser page with the Jitsi iframe API. It can observe structured meeting events:

- local user joined;
- participant joined/left;
- participant role changed;
- recording status changed;
- transcription chunks received, if transcription is enabled and supported;
- recording link became available.

This lets the agent respond to meeting structure, but not to raw speech unless transcription events are present.

### Level 3: Transcript-Aware Assistant

The agent gets live transcript chunks and uses them to:

- track agenda progress;
- detect decisions;
- detect action items;
- answer "what did we just decide?";
- remind the group about time boxes;
- produce live notes.

This can work through Jitsi's built-in transcription if the deployment supports it, or through an external ASR path.

### Level 4: Full Media Participant

The agent joins as a real participant using `lib-jitsi-meet`, the iframe in a headless browser, or browser automation. It subscribes to audio tracks and streams them to ASR.

This gives the most control, but it is much harder:

- WebRTC needs a browser-like runtime;
- audio capture and mixing need engineering;
- speaker attribution is nontrivial;
- E2EE can block server-side media processing unless the agent is a legitimate endpoint with keys;
- consent and privacy UX become product-critical.

## Would It Need Whisper Or Another ASR API?

If the agent should understand spoken words during the meeting, yes, it needs a transcript source.

Options:

1. Use Jitsi built-in transcription if available.
2. Record first, then transcribe after the meeting.
3. Join as a bot/participant, capture audio, and stream it to Whisper or another ASR service.

For a first prototype, use built-in Jitsi transcription events if a controlled deployment supports them. If not, use post-meeting transcription. Live custom ASR is the most powerful path, but it should come after the scheduling/permission/artifact workflow is working.

## How Does The Existing `teexai-transcribe` Prototype Change This?

It makes the live-transcription part much more reasonable than starting from scratch.

The current repo already has a credible ASR/meeting-notes backend in `teexai-transcribe`:

- browser mic capture with repeated short uploads;
- `/api/transcribe` for chunked Whisper-large-v3 transcription through near.ai;
- `/api/transcribe_diarized` for final diarization inside the CVM with sherpa-onnx/pyannote/wespeaker;
- `/api/enroll` and `/api/voiceprints` for speaker identity enrollment;
- transcript summarization and action-item extraction via `/api/chat/stream`;
- a small tool-using `/api/agent` endpoint that can act on the transcript;
- a TEE-oriented privacy architecture where diarization/voiceprints stay in the CVM.

That means the meeting-skill question is not "can we build transcription?" The question is "how do we feed meeting audio into this service cleanly?"

There are three plausible bridges:

1. Browser-tab capture: run Jitsi in the same controlled browser context and capture tab/system audio for `teexai-transcribe`.
2. Bot participant: join Jitsi as an agent participant and capture subscribed audio tracks.
3. Recording-first: use Jitsi/Jibri/local recording, then send the saved audio/video file to `/api/transcribe_diarized`.

For an early demo, browser capture or recording-first is probably enough. For a proper live meeting companion, a bot participant or a dedicated Jitsi iframe/control page should stream chunks into the existing `/api/transcribe` path, then run final diarization at the end.

## Is Jitsi Easy To Test?

It depends on what is being tested.

Easy:

- room URL generation;
- calendar invite creation;
- agenda/context generation;
- post-meeting summarization from a saved transcript;
- iframe API event handling with mocked events;
- permission-policy logic.

Moderate:

- iframe API integration against a live Jitsi deployment;
- joining a room with one or two browser participants;
- verifying participant join/leave events;
- verifying recording/transcription controls on a configured deployment.

Hard:

- reliable multi-browser WebRTC tests;
- audio quality tests;
- NAT/TURN failure tests;
- recording pipeline tests with Jibri;
- live ASR from actual remote audio;
- mobile tests;
- load tests.

Jitsi has a Selenium-based test framework called `jitsi-meet-torture`. It runs browser/mobile participants against a Jitsi Meet instance and can run selected tests with Maven, for example:

```bash
mvn test -Djitsi-meet.instance.url="https://meet.example.com"
```

It also has iframe API tests and load-test tooling. This is useful for testing Jitsi itself or a serious self-hosted deployment, but it is heavy for a first agent-skill prototype.

For this project, the pragmatic test strategy is:

1. Unit-test meeting planning and permissions without Jitsi.
2. Mock iframe events and test the agent's state machine.
3. Run a small Playwright test with two browser tabs against a Jitsi room.
4. Add one live smoke test against a controlled Jitsi server.
5. Only use `jitsi-meet-torture` if we start operating Jitsi infrastructure seriously.

## Recommended First Agent Design

Start with:

- generate high-entropy Jitsi room URLs;
- create calendar invites;
- prepare agenda/context;
- require explicit policy for recording/transcription;
- optionally open an iframe-control page;
- consume live transcription only if available;
- otherwise process a post-meeting transcript/recording.

Do not start by building a full WebRTC bot. That is possible, but it is not the first useful version.
