# Jitsi-Powered Meeting Skill Research

Date: 2026-06-03

This is an initial technical and product research memo for building an agent skill around Jitsi-powered meetings. The intended skill is not just "join a video call"; it should help plan, convene, govern, capture, transcribe, and follow up on meetings while making the permission boundaries explicit.

## Executive Summary

Jitsi is a good fit for an agent-mediated meeting workflow because rooms are URL-addressable, self-hosting is realistic, and the browser/client APIs expose enough meeting state to support high-level meeting automation. The best first prototype is probably not a fully headless WebRTC bot. It is a Jitsi meeting coordinator skill that can create deterministic or random room URLs, add them to calendar invites, prepare an agenda/context packet, enforce host/lobby/recording/transcription policy, and then either embed a Jitsi iframe for human control or run a supervised meeting companion that listens to iframe events.

The deeper integration path is possible, but harder. Jitsi has a low-level `lib-jitsi-meet` API that can join rooms, subscribe to tracks, observe participants, and act without the stock UI. That is the right place to build a true meeting bot, but it brings WebRTC runtime requirements, audio capture/processing, deployment complexity, and moderation/privacy issues. The iframe API is much easier for a "control surface" or "operator dashboard"; `lib-jitsi-meet` is better for a durable agent participant.

Key design conclusion: model the skill around meeting outcomes, not around WebRTC. The skill should expose verbs such as `schedule_meeting`, `prepare_agenda`, `start_room`, `admit_participants`, `start_transcription`, `capture_decisions`, `summarize_followups`, and `publish_minutes`. Jitsi becomes the transport and governance substrate.

## Primary Sources

- [Jitsi architecture handbook](https://jitsi.github.io/handbook/docs/architecture)
- [Jitsi iframe API](https://jitsi.github.io/handbook/docs/dev-guide/dev-guide-iframe)
- [Jitsi iframe commands](https://jitsi.github.io/handbook/docs/dev-guide/dev-guide-iframe-commands/)
- [Jitsi iframe events](https://jitsi.github.io/handbook/docs/dev-guide/dev-guide-iframe-events)
- [Jitsi configuration reference](https://jitsi.github.io/handbook/docs/dev-guide/dev-guide-configuration/)
- [lib-jitsi-meet low-level API guide](https://jitsi.github.io/handbook/docs/dev-guide/dev-guide-ljm-api/)
- [lib-jitsi-meet API reference](https://jitsi.github.io/lib-jitsi-meet/)
- [Jitsi Docker self-hosting guide](https://jitsi.github.io/handbook/docs/devops-guide/devops-guide-docker)
- [Jitsi authentication guide](https://jitsi.github.io/handbook/docs/devops-guide/authentication/)
- [Jitsi secure domain setup](https://jitsi.github.io/handbook/docs/devops-guide/secure-domain)
- [Jitsi token authentication](https://jitsi.github.io/handbook/docs/devops-guide/token-authentication/)
- [Jitsi requirements and recording notes](https://jitsi.github.io/handbook/docs/devops-guide/devops-guide-requirements/)
- [Jitsi security and privacy overview](https://jitsi.org/security/)
- [Jitsi E2EE overview](https://jitsi.org/e2ee-in-jitsi/)
- [MDN WebRTC protocol overview](https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API/Protocols.)
- [WebRTC peer connection guide](https://webrtc.org/getting-started/peer-connections)
- [IETF RFC 8827, WebRTC Security Architecture](https://datatracker.ietf.org/doc/html/rfc8827)
- [IETF RFC 8835, WebRTC Transports](https://www.ietf.org/rfc/rfc8835.html)
- [IETF RFC 8656, TURN](https://www.ietf.org/rfc/rfc8656.html)

## How Jitsi Works

Jitsi Meet is not one server. It is a set of cooperating components:

- Jitsi Meet web app: the React/browser client that users see.
- Jitsi Videobridge, or JVB: the WebRTC media router. It is an SFU, not an MCU. It forwards selected media streams instead of mixing all video into one composed stream.
- Jicofo: the conference focus. It coordinates conferences, allocates/controls videobridges, and manages conference-level decisions.
- Prosody: the XMPP server used for signaling, room membership, presence, roles, and extensions.
- Jibri: the recording/streaming worker. It joins a conference with Chrome in a virtual display and captures/encodes with ffmpeg.
- Jigasi: a gateway for SIP participants and related gateway use cases.
- Web server/reverse proxy: serves the web client and proxies signaling endpoints.
- TURN/STUN service, often coturn: improves connectivity through restrictive networks.

There are two planes:

- Control/signaling plane: browser client to Prosody/Jicofo over XMPP via WebSocket or BOSH. This carries join/leave, presence, roles, moderation, source signaling, chat-like messages, and conference state.
- Media plane: browser client to another browser in P2P mode or to JVB in multi-party mode using WebRTC transports, typically ICE + DTLS-SRTP over UDP.

The normal room lifecycle looks like this:

1. A user opens a URL such as `https://meet.example.com/room-name`.
2. The Jitsi web app loads `config.js`, `interface_config.js`, and the app bundle.
3. The user may pass through prejoin, auth, lobby, or password flows depending on config.
4. The client connects to Prosody and joins an XMPP MUC room for the conference.
5. Jicofo becomes the focus for the conference and coordinates bridge allocation.
6. For a 1:1 call, Jitsi may use peer-to-peer media directly between browsers.
7. For a group call, JVB receives encrypted media from each participant and forwards selected streams to others.
8. Moderation, lobby, recording, transcription, and chat are represented as conference state/events over the signaling layer.
9. When all participants leave, the room state is normally ephemeral unless backed by extra services.

Room names matter. On a public unauthenticated instance, a simple reusable name like `weekly` is guessable and collides with other users. For an agent skill, room creation should generate names with enough entropy, and user-facing aliases should be mapped to opaque room URLs.

## Jitsi Deployment Choices

### Public `meet.jit.si`

This is the lowest-friction way to test human flows: create a room URL and invite people. It is poor as the foundation for a reliable agent product because you do not control auth policy, recording/transcription configuration, retention, rate limits, branding, moderation, or API guarantees. Public-service behavior also changes over time; current docs and Jitsi pages should be checked before relying on embedding or bot behavior.

### Self-hosted Jitsi

This gives maximum control over:

- whether unauthenticated users may create rooms;
- whether guests must wait for a host;
- JWT-based room access;
- lobby and password policy;
- recording/transcription services;
- TURN behavior and network reachability;
- data retention and logs;
- custom Prosody modules or web hooks.

The operational cost is real. A basic Meet/Jicofo/Prosody/JVB setup is straightforward, but Jibri is resource-heavy. Jitsi's requirements docs say one Jibri instance handles one recording at a time, and recording needs much more CPU/RAM/disk than normal conferencing. If the agent skill promises automatic recording at scale, Jibri capacity planning becomes part of the product.

### JaaS

Jitsi as a Service is likely the fastest path for a production hosted app that wants official support, iframe APIs, JWT auth, and less self-hosting burden. It is less aligned with maximum privacy/control than self-hosting, but it reduces operational risk.

### Hybrid

For research/prototype:

- use public Jitsi for basic room scheduling and manual flow tests;
- use local/self-hosted Jitsi for controlled auth/transcription/recording experiments;
- evaluate JaaS if the skill needs embedded meetings in a public app quickly.

## WebRTC Mechanics Relevant To Jitsi

WebRTC exposes three main browser APIs:

- `getUserMedia`: obtain microphone/camera tracks from the browser.
- `RTCPeerConnection`: negotiate and transport audio/video/data between peers or between a browser and an SFU.
- `RTCDataChannel`: send arbitrary data over SCTP/DTLS/ICE.

WebRTC requires signaling, but does not specify the signaling protocol. Each app chooses its own signaling channel. Jitsi uses XMPP via Prosody for that layer. The signaling channel exchanges session descriptions, ICE candidates, participant state, media-source metadata, roles, chat, and conference control messages.

Core protocol pieces:

- SDP: a description format for capabilities, codecs, tracks, ICE credentials, DTLS fingerprints, and media sections.
- Offer/answer: the negotiation pattern where one endpoint proposes a session and the other answers.
- ICE: the framework for discovering viable network paths between endpoints.
- STUN: lets a client discover its public-facing network address and NAT behavior.
- TURN: relays traffic when direct paths fail or when privacy policy requires relay-only connectivity.
- DTLS: authenticates/encrypts transport and establishes keys.
- SRTP: carries encrypted real-time audio/video packets.
- RTP/RTCP: media transport and feedback/control for real-time streams.
- SCTP over DTLS: used by WebRTC data channels.

Important mental model:

- WebRTC media can be peer-to-peer, but production meetings often use SFUs.
- A TURN server relays packets but should not decrypt media; media remains protected by DTLS-SRTP between WebRTC endpoints. In an SFU architecture, the SFU is a WebRTC endpoint for transport purposes.
- In a Jitsi group call, transport encryption terminates at JVB so it can inspect routing metadata and forward media. Jitsi E2EE adds a second layer using insertable streams so the bridge can route without reading frame contents, but that changes feature compatibility and browser/runtime assumptions.
- ICE failure is one of the most common real-world WebRTC reliability problems. Enterprise firewalls, symmetric NATs, UDP blocking, TLS interception, or missing TURN can break otherwise correct applications.

For an agent skill, most of this should be hidden. The skill should expose meeting-level behavior and only surface WebRTC diagnostics when a meeting cannot connect or record.

## Integration Options

### Option 1: Iframe API Control Surface

The iframe API embeds Jitsi Meet and exposes a `JitsiMeetExternalAPI` object. This is the easiest way to build a meeting console or agent-supervised UI.

It supports:

- creating/loading a room inside an app;
- passing JWTs;
- setting `roomName`, `userInfo`, `configOverwrite`, and `interfaceConfigOverwrite`;
- invoking commands such as mute, hangup, subject changes, display name changes, tile view, and recording/transcription controls;
- listening for events such as participant join/leave, conference joined/left, role changes, mute changes, recording status, recording link availability, and transcription chunks.

Useful events for an agent:

- `videoConferenceJoined`
- `participantJoined`
- `participantLeft`
- `participantRoleChanged`
- `participantMuted`
- `recordingStatusChanged`
- `recordingLinkAvailable`
- `transcriptionChunkReceived`
- `passwordRequired`
- `readyToClose`
- `p2pStatusChanged`

Useful commands for an agent:

- `displayName`
- `subject`
- `toggleAudio`
- `toggleVideo`
- `hangup`
- `startRecording`
- `stopRecording`
- `password`
- moderation-related commands, depending on deployment and role

This option is best for:

- a browser-based agent dashboard;
- a human operator supervising the agent;
- meeting state capture without a full custom media stack;
- a first prototype.

Limitations:

- The Jitsi UI still exists inside the iframe.
- The agent is constrained by browser session state and user permissions.
- For unattended bot behavior, the browser must remain running.
- Access to raw media tracks is not the primary abstraction.

### Option 2: `lib-jitsi-meet` Bot Or Custom Client

`lib-jitsi-meet` is the low-level JavaScript API under the Jitsi UI. It exposes `JitsiConnection`, `JitsiConference`, tracks, participants, and conference events.

The rough join flow:

1. Load/init `JitsiMeetJS`.
2. Create a `JitsiConnection` with deployment options.
3. Listen for connection success/failure/disconnect.
4. Initialize a `JitsiConference`.
5. Attach conference listeners.
6. Optionally create local audio/video tracks.
7. Call `room.join()`.
8. Subscribe to remote tracks and events.

This is the likely path for a real agent participant:

- join as `Meeting Agent`;
- remain muted or publish a synthetic/silent audio track if required;
- observe participants and metadata;
- subscribe to audio tracks for external transcription;
- send chat/status messages;
- expose meeting-state events to the agent runtime;
- optionally control moderation if authenticated as host.

Limitations:

- You still need a WebRTC-capable runtime. In practice, headless Chrome/Playwright is often simpler than trying to run browser WebRTC inside pure Node.
- Raw audio capture from remote tracks has to be engineered and tested carefully.
- Bot detection, duplicate identity, host permissions, and privacy notifications matter.
- E2EE may prevent server-side/bot transcription unless the bot is a legitimate participant with keys.

### Option 3: Direct XMPP/Prosody Integration

An agent could connect to Prosody as an XMPP client or use custom Prosody modules. This is useful for server-side policy, room metadata, audit events, or webhooks.

This is not the right first path for media or transcription. Jitsi's behavior is encoded in XMPP extensions and app conventions; direct XMPP control is powerful but brittle unless you own the deployment.

### Option 4: Jibri Recording Worker

Jibri joins a meeting as a special participant and records/streams the rendered conference. This is the official path for server-side recording/streaming in self-hosted deployments.

This is best when the desired artifact is video/audio recording, not just transcript text. It is expensive: one Jibri per simultaneous recording is the operational planning rule from the Jitsi docs.

### Option 5: Local Recording

Jitsi has local recording options that save in the user's device storage. This can be simple and privacy-friendly, but it is not a reliable unattended agent mechanism because it depends on a participant browser and browser storage APIs.

### Option 6: External Transcription

Instead of using Jitsi's built-in transcription, the agent can join as a participant, capture audio, and stream it to an external ASR pipeline. This gives maximum model/control flexibility and integrates well with post-meeting workflows, but it has the highest engineering and consent burden.

## Authentication, Roles, And Permissions

Jitsi can be run with open room creation, secure domain auth, or JWT token auth.

For agent use, the important policies are:

- Who may create a room?
- Who becomes moderator?
- Can guests join before a host?
- Can the agent admit lobby users?
- Can the agent start recording/transcription?
- Can the agent kick/mute participants?
- Can the agent see participant names/emails?
- Can the agent publish transcripts or summaries automatically?

Secure domain setup allows only authenticated users to create rooms while guests can join after the room exists. Token auth allows valid JWTs to govern access, identity, room scope, and sometimes moderator behavior depending on server configuration.

The skill should have explicit permission scopes rather than treating "join meeting" as one permission:

- `calendar:read_freebusy`
- `calendar:create_event`
- `calendar:update_event`
- `contacts:read`
- `jitsi:create_room`
- `jitsi:host_room`
- `jitsi:admit_lobby`
- `jitsi:moderate_audio_video`
- `jitsi:start_recording`
- `jitsi:start_transcription`
- `meeting:read_live_transcript`
- `meeting:publish_minutes`
- `meeting:send_followups`

The agent should ask for approval before starting recording/transcription unless a standing meeting policy exists. It should also make the active recording/transcription state visible to participants.

## Transcription Paths

There are three plausible approaches:

### Built-In Jitsi Transcription

Jitsi iframe commands allow `startRecording` with transcription enabled, and iframe events can emit transcription chunks. Jitsi config has a `transcription` block with settings for enabling transcription, language choices, and auto-transcription-on-record behavior.

This is attractive because the meeting platform owns the UX and participant notifications. The challenge is deployment support: not every public or self-hosted instance will have transcription configured. This needs a controlled deployment or JaaS feature confirmation.

### Recording First, Transcribe After

Use Jibri/file/local recording, then run post-meeting transcription on the resulting audio/video. This is robust for minutes and summaries, but not useful for live facilitation. It also delays output and requires recording storage governance.

### Agent Participant Live ASR

The agent joins the call, subscribes to audio, separates speakers as well as possible, and streams audio to an ASR system. This enables live agenda tracking, reminders, decision capture, and action-item extraction. It is also the most complex path technically and socially.

Recommendation:

- Prototype with Jitsi iframe transcription events if available.
- Build a fallback path from recording to post-meeting transcription.
- Treat custom live ASR bot as a second-stage research project.

## Skill Product Model

The skill should be organized by meeting phases.

### 1. Meeting Planning

Responsibilities:

- infer purpose and desired outcome;
- propose agenda;
- choose attendees;
- inspect calendars/free-busy;
- generate a Jitsi room URL;
- decide whether the room should be public, passworded, lobby-gated, or JWT-gated;
- create/update calendar invites;
- attach agenda/context;
- prepare pre-read material.

Potential tool:

```json
{
  "name": "schedule_jitsi_meeting",
  "input": {
    "title": "string",
    "outcome": "string",
    "attendees": ["email"],
    "duration_minutes": 45,
    "time_window": "natural language or structured range",
    "agenda": ["string"],
    "security": {
      "room_entropy": "high",
      "lobby": true,
      "password": "auto",
      "host_required": true
    },
    "recording_policy": "ask-at-start | always | never",
    "transcription_policy": "ask-at-start | always | never"
  }
}
```

### 2. Pre-Meeting Preparation

Responsibilities:

- assemble context packet from docs/tickets/emails;
- identify unresolved decisions;
- produce facilitator notes;
- detect missing required participants;
- check whether the Jitsi room is reachable;
- optionally pre-warm the room as host.

Potential tool:

```json
{
  "name": "prepare_meeting_context",
  "input": {
    "calendar_event_id": "string",
    "source_refs": ["document/task/email ids"],
    "desired_outputs": ["decisions", "risks", "owners", "next steps"]
  }
}
```

### 3. Convening

Responsibilities:

- open/start the room;
- join as host or companion;
- admit lobby participants;
- set subject;
- paste agenda in chat;
- announce recording/transcription policy;
- start transcription if approved;
- watch for missing/late participants.

Potential tool:

```json
{
  "name": "start_jitsi_session",
  "input": {
    "room_url": "string",
    "display_name": "Meeting Agent",
    "join_mode": "host | companion | observer",
    "start_transcription": false,
    "start_recording": false
  }
}
```

### 4. Live Meeting Assistance

Responsibilities:

- track agenda progress;
- detect explicit decisions;
- detect action items;
- maintain a parking lot;
- answer "what did we decide?" from transcript context;
- remind participants of time boxes;
- manage recording/transcription state;
- optionally create issues/tasks during the meeting.

The key design question is how intrusive the agent should be. Initial mode should be passive and chat-based, with explicit user commands such as:

- "agent, capture that as a decision"
- "agent, make Alice owner of the follow-up"
- "agent, add that to parking lot"
- "agent, summarize where we are"

### 5. Post-Meeting

Responsibilities:

- finalize transcript;
- produce minutes;
- extract decisions, action items, owners, due dates;
- link recording/transcript artifacts;
- request user approval before sending;
- update calendar event/docs/tasks;
- send follow-up email/chat.

Potential output schema:

```json
{
  "meeting_id": "string",
  "title": "string",
  "participants": ["string"],
  "summary": "string",
  "decisions": [
    {
      "decision": "string",
      "rationale": "string",
      "timestamp": "string",
      "confidence": 0.0
    }
  ],
  "action_items": [
    {
      "task": "string",
      "owner": "string",
      "due": "string",
      "source_timestamp": "string"
    }
  ],
  "open_questions": ["string"],
  "parking_lot": ["string"],
  "artifacts": {
    "room_url": "string",
    "recording_url": "string",
    "transcript_url": "string"
  }
}
```

## Candidate Architecture For A Prototype

### Minimal Prototype

Build a skill that:

1. Generates secure Jitsi room names.
2. Creates calendar events with the Jitsi link and agenda.
3. Stores meeting metadata locally.
4. Opens an iframe-based meeting control page.
5. Listens to iframe events for participants and recording/transcription status.
6. Captures transcription chunks if the deployment emits them.
7. Produces post-meeting summary artifacts.

This does not require raw WebRTC handling.

### Prototype Components

- Skill manifest: exposes meeting tools.
- Room service: generates/validates Jitsi URLs and optional JWTs.
- Calendar adapter: Google/Microsoft/CalDAV later; local `.ics` first is enough for a demo.
- Meeting metadata store: room, agenda, attendees, policies, transcript status.
- Jitsi control page: iframe API integration.
- Event collector: normalizes Jitsi events.
- Transcript collector: consumes `transcriptionChunkReceived` if present.
- Summary pipeline: converts transcript/events into decisions and action items.

### Controlled Deployment Prototype

Run self-hosted Jitsi with Docker:

- enable auth or JWT;
- configure guest/lobby behavior;
- configure recording/transcription;
- configure TURN;
- test iframe API from a local app;
- test Jibri capacity and recording artifact path.

This gives the agent reliable permissions instead of relying on public `meet.jit.si` behavior.

### Full Bot Prototype

Use `lib-jitsi-meet` or headless browser automation:

- join as a participant;
- subscribe to remote audio tracks;
- feed audio into an ASR service;
- emit structured live transcript events;
- support chat commands;
- maintain a meeting state machine.

This is the most interesting long-term path but should follow the iframe/control prototype.

## Major Risks And Open Questions

- Public Jitsi service policy: whether public `meet.jit.si` allows the embedding/auth/bot behavior needed for your use case may change and should not be treated as a stable backend.
- Transcription availability: built-in transcription depends on deployment config and backend services.
- Recording capacity: Jibri is one-recording-per-instance; automatic recording needs infrastructure planning.
- Consent: recording/transcription needs participant-visible notification and explicit policy.
- E2EE: if enabled, server-side recording/transcription or bridge-level processing may not work as expected. A bot participant can receive decrypted media only if it is a legitimate endpoint with keys.
- Speaker attribution: Jitsi participant metadata helps, but transcription speaker labels depend on the transcription path.
- Headless operation: browser audio/WebRTC in CI/server environments is fragile. Headless Chrome is practical but operationally heavier than a normal HTTP service.
- Moderation authority: role assignment requires correct auth/JWT/Prosody/Jicofo configuration.
- Calendar authority: scheduling as the user requires separate OAuth scopes and a human-in-the-loop approval model.
- Data retention: transcripts and recordings are sensitive and need retention/deletion policies from day one.

## Recommended Next Experiments

1. Build a throwaway iframe API page that joins a room and logs all events.
2. Verify current public `meet.jit.si` behavior for iframe embedding, host requirements, and transcription controls.
3. Spin up self-hosted Jitsi via Docker and test secure domain/JWT room creation.
4. Test `startRecording` with local/file/transcription modes on a controlled deployment.
5. Test whether transcription chunks are emitted through the iframe API and what payload quality looks like.
6. Prototype secure room-name generation and calendar invite creation.
7. Sketch the skill API around meeting phases and permission scopes.
8. Only after those succeed, attempt a `lib-jitsi-meet` companion bot that joins and observes tracks.

## Practical Recommendation

The first deliverable should be a "Jitsi meeting coordinator" skill, not a "Jitsi WebRTC bot." It should create and manage meeting containers: room, agenda, invite, host policy, transcript/recording policy, and follow-up artifacts. Then add live meeting supervision through the iframe API. A true media bot should be a later layer once the meeting workflow and permission model are right.

