# Alternatives To Jitsi For An Agentic Meeting Skill

Date: 2026-06-03

This memo compares alternatives to Jitsi for building an agentic meeting skill: something that can schedule meetings, prepare context, join or supervise calls, manage recording/transcription permissions, capture decisions, and produce follow-ups.

The main conclusion: if the goal is an agent-native meeting runtime, LiveKit is the strongest alternative to investigate next. If the goal is a self-hosted turnkey classroom/meeting platform, BigBlueButton is the most mature alternative. If the goal is compatibility with meetings people already use, Teams, Google Meet, and Zoom are unavoidable, but they produce a very different skill: more of a meeting-artifact collector and scheduler than a deeply embedded meeting participant.

## Primary Sources

- [LiveKit overview](https://docs.livekit.io/intro/about)
- [LiveKit SFU internals](https://docs.livekit.io/reference/internals/livekit-sfu)
- [LiveKit Agents JS reference](https://docs.livekit.io/reference/agents-js/)
- [BigBlueButton API reference](https://docs.bigbluebutton.org/development/api/)
- [BigBlueButton recording docs](https://docs.bigbluebutton.org/2.6/development/recording/)
- [Janus recordings docs](https://janus.conf.meetecho.com/docs/recordings.html)
- [mediasoup documentation](https://mediasoup.org/documentation/v3/mediasoup/)
- [Galene homepage](https://galene.org/)
- [Galene documentation](https://galene.org/galene.html)
- [MiroTalk SFU docs](https://docs.mirotalk.com/mirotalk-sfu/)
- [Element Call setup docs](https://docs.element.io/latest/element-server-suite-classic/integrations/setting-up-element-call/)
- [Microsoft Teams transcripts and recordings via Graph](https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/meeting-transcripts/overview-transcripts)
- [Google Meet artifacts API](https://developers.google.com/workspace/meet/api/guides/artifacts)
- [Zoom Meetings API docs](https://godevelopers.zoom.us/docs/api/meetings/)
- [Daily transcription docs](https://docs.daily.co/guides/products/transcription)
- [Daily AI transport docs](https://daily-co.github.io/dailyai-docs/docs/api-reference/transports/daily-transport)

## Evaluation Criteria

For a normal meeting product, the obvious criteria are call quality, UX, mobile support, cost, and recording. For an agentic meeting skill, the more important criteria are:

- Can the agent create rooms programmatically?
- Can it join as a first-class participant?
- Can it get live participant, track, chat, recording, and transcription events?
- Can it access raw or structured audio safely for ASR?
- Can recording and transcription be consented to and audited?
- Can the platform enforce host/lobby/guest permissions?
- Can the platform produce post-meeting artifacts through an API?
- Can it be self-hosted, or does it require a cloud vendor?
- Can it integrate with calendars and identity providers?
- Does it already have an agent/bot abstraction?

## Shortlist

### 1. LiveKit

LiveKit is the most agent-native option. It is an open-source WebRTC SFU plus a cloud platform, SDK ecosystem, room APIs, recording/streaming via Egress, external media ingestion via Ingress, SIP/telephony, and an explicit Agents framework. Its docs now describe it as a framework and cloud platform for voice, video, and physical AI agents, which is directly aligned with this project.

Why it matters:

- It is not primarily a finished video meeting app; it is programmable real-time infrastructure.
- Agents are a first-class use case rather than an afterthought.
- The server is an SFU, so the agent can join a room and subscribe to individual tracks.
- Room/session management can be modeled cleanly with tokens and server APIs.
- It supports both self-hosting and hosted cloud.
- It has a path for real-time voice agents, live transcription, telephony, and data channels.

Agentic meeting fit:

- Excellent for a custom meeting experience.
- Excellent for an agent participant that needs audio tracks, turn-taking, speech events, and low-latency interaction.
- Strong for "agent convenes a meeting room, joins as facilitator, listens, speaks, and produces artifacts."
- We would need to build or choose the meeting UI, calendar integration, agenda flow, and post-meeting artifact model.

Tradeoffs:

- Less turnkey than Jitsi or BigBlueButton if we want a complete human meeting app immediately.
- More engineering surface: UI, room policy, recording UX, participant controls, and artifact workflows.
- For self-hosted distributed scale, Redis and operational planning enter the picture.

Verdict:

Best next technical investigation if the priority is an agent-first meeting skill rather than a generic video meeting replacement.

### 2. BigBlueButton

BigBlueButton is a mature open-source web conferencing system oriented toward virtual classrooms, webinars, presentations, whiteboards, and LMS integration. It has a well-established HTTP API for creating meetings, joining users, managing recordings, metadata, and integrations. It has stronger built-in meeting pedagogy than Jitsi: presentations, whiteboard, breakout workflows, roles, learning analytics, and recording pipelines are central.

Why it matters:

- It is closer to a "structured meeting session" than a bare video room.
- The API is designed for external systems to create/join/manage meetings.
- Recording and post-processing are core parts of the system.
- It already has roles such as moderator/viewer and many classroom-style controls.

Agentic meeting fit:

- Strong for scheduled, structured meetings where the agent is a coordinator/facilitator.
- Strong for agenda-driven sessions, lectures, working groups, and workshops.
- Good for post-meeting artifact workflows because recordings and metadata are built in.
- Good if the agent is attached to a calendar/LMS/workflow app that creates meetings.

Tradeoffs:

- Heavier operationally than a small LiveKit or Galene deployment.
- Less agent-native than LiveKit; raw media and live conversational agent behavior are not the primary abstraction.
- The UX/product assumptions are education/webinar heavy.

Verdict:

Best alternative if the skill wants a self-hosted, open-source, structured meeting platform with robust room APIs and recording.

### 3. Daily

Daily is a commercial WebRTC platform with APIs for rooms, participants, recording, real-time transcription, and AI/bot transports. Daily is not an open-source self-hosted stack, but it is highly relevant because it targets exactly the "build real-time meeting apps and bots" problem.

Why it matters:

- Real-time transcription is a documented product feature.
- Daily AI transport is explicitly built to join bots to Daily WebRTC calls.
- It reduces infrastructure burden.
- It is likely faster than self-hosting for a production prototype.

Agentic meeting fit:

- Strong for agent participants and live transcription.
- Strong for a hosted product prototype where we care more about agent workflows than owning media servers.
- Useful benchmark for how an agent meeting skill should feel.

Tradeoffs:

- Vendor dependency.
- Privacy/control depends on Daily's product and contracts.
- Less aligned with "self-host everything."

Verdict:

Strong hosted alternative. Worth testing if speed matters more than full infrastructure ownership.

### 4. Zoom

Zoom is not a Jitsi-like open-source alternative, but it is unavoidable for compatibility. It has meeting APIs, recordings, transcripts, summaries, SDKs, webhooks, and bot/meeting SDK paths. For an agent skill, Zoom is probably less about controlling the meeting runtime and more about scheduling, joining, and retrieving artifacts.

Why it matters:

- Many users already hold meetings there.
- Recordings/transcripts/summaries can be retrieved through APIs under the right account settings and permissions.
- Meeting SDK/bot approaches can join meetings, but permissions and marketplace/account constraints matter.

Agentic meeting fit:

- Strong for "my agent should attend/summarize existing Zoom meetings."
- Strong for post-meeting artifact ingestion.
- Moderate for scheduling and convening.
- Weaker for deeply customizing the meeting experience.

Tradeoffs:

- Closed platform and permission-heavy.
- API access depends on account settings, scopes, host consent, and sometimes admin approval.
- Bot behavior may be constrained by marketplace/platform policy.

Verdict:

Good compatibility target, not the best foundation for an open agent-native meeting stack.

### 5. Microsoft Teams

Teams is a strong enterprise target because Microsoft Graph exposes online meetings, transcripts, recordings, notifications, and meeting/call artifacts. It also has tenant, app, and resource-specific consent models. Like Zoom, this is less about owning the meeting runtime and more about integrating with the enterprise meeting system of record.

Why it matters:

- Graph APIs can fetch meeting transcripts and recordings after they are generated.
- Permissions can be tenant-wide or meeting-specific.
- Microsoft documents notification flows for when transcripts/recordings become available.
- Teams is often where enterprise calendar, identity, and meeting policy already live.

Agentic meeting fit:

- Strong for enterprise post-meeting intelligence.
- Strong for calendar-driven scheduled meetings.
- Good for compliance-aware artifact retrieval.
- Less suitable for an open self-hosted meeting runtime.

Tradeoffs:

- Tenant/admin permission complexity.
- Some APIs are metered or have licensing/commercial implications.
- Live in-meeting agent behavior is possible, but platform-specific and heavier than a WebRTC-native stack.

Verdict:

Essential enterprise integration target, especially for transcript/recording retrieval and follow-up generation.

### 6. Google Meet

Google Meet has Workspace APIs for meeting spaces and conference records/artifacts, including transcripts and recordings when generated. It is similar to Teams as an integration target: useful for existing meetings and artifacts, not ideal if we want to own the meeting runtime.

Why it matters:

- Google Meet artifacts API can retrieve details about generated artifacts.
- Google docs state transcripts operate independently of recordings.
- Calendar and Meet integration are natural in Google Workspace environments.

Agentic meeting fit:

- Strong for "meeting artifact collector" workflows.
- Strong if the user already schedules through Google Calendar.
- Weaker for live agent participation and deep meeting control.

Tradeoffs:

- Closed platform and Workspace permission model.
- Runtime customization is limited.
- Bot participation usually requires browser automation or third-party meeting bot infrastructure.

Verdict:

Important compatibility target for Google Workspace users, but not the best base for a custom agentic meeting system.

### 7. Element Call / MatrixRTC

Element Call is Matrix's next-generation calling stack and is moving toward LiveKit-backed SFU architecture for group calls. It is compelling if the long-term goal involves federated identity, rooms, chat history, and decentralized collaboration.

Why it matters:

- Matrix already has durable rooms, identity, messages, files, bots, and federation.
- Calls can be part of a larger collaboration room rather than isolated meeting URLs.
- Element documentation describes Element Call as replacing Jitsi in the Matrix/Element stack.

Agentic meeting fit:

- Strong if meetings should live inside persistent collaboration rooms.
- Strong if the agent is also a Matrix bot.
- Interesting for "meeting as a room event stream" rather than "meeting as a video URL."

Tradeoffs:

- The calling stack is newer and more moving-target than Jitsi/BBB.
- Self-hosting Matrix + Element Call + LiveKit is operationally involved.
- Documentation and deployment patterns are less simple than a standalone LiveKit prototype.

Verdict:

Strategically interesting if persistent/federated collaboration matters. Not the fastest path to a meeting-agent prototype.

### 8. Galene

Galene is a lightweight self-hosted WebRTC videoconference server written in Go using Pion. It emphasizes simplicity, moderate resource usage, lectures, conferences, tutorials, and meetings. It has recording to disk, public/private groups, subgroups, and a built-in TURN server.

Why it matters:

- Much lighter than Jitsi or BigBlueButton.
- Self-hosting is simple.
- Recording exists.
- Groups can be generated/configured.

Agentic meeting fit:

- Good for small, self-hosted, privacy-oriented experiments.
- Good if we want to understand a minimal WebRTC meeting server.
- Less strong for rich APIs, agent SDKs, calendar integration, or enterprise controls.

Tradeoffs:

- Smaller ecosystem.
- Less turnkey for agent APIs.
- No explicit agent/bot framework.

Verdict:

Good lightweight research target, especially if the question is "what is the minimum self-hosted meeting substrate?"

### 9. MiroTalk

MiroTalk is an open-source WebRTC meeting suite, with SFU mode powered by mediasoup. It advertises rooms, screen sharing, chat, recording, whiteboard, file sharing, REST API, RTMP streaming, and AI features.

Why it matters:

- More turnkey meeting UI than raw mediasoup.
- Self-hosted.
- Built on a mature SFU library.
- Potentially quicker than building a custom mediasoup app.

Agentic meeting fit:

- Good as a Jitsi-like self-hosted alternative to test.
- Potentially useful if the REST API and AI hooks fit the agent workflow.
- Less foundationally agent-native than LiveKit.

Tradeoffs:

- Need deeper review of licensing, architecture, production maturity, and API completeness.
- "AI features" should be verified in code/docs before relying on them.

Verdict:

Worth a secondary look, especially as a practical self-hosted meeting app built on mediasoup.

### 10. mediasoup

mediasoup is a low-level SFU toolkit: a C++ worker with Node.js server APIs for building custom WebRTC media systems. It is not a meeting app. It is infrastructure for teams that want to own signaling, room logic, track routing, and UI.

Why it matters:

- Maximum control.
- Mature in custom WebRTC deployments.
- Good when the product's media behavior is unusual.

Agentic meeting fit:

- Strong only if we want to build the full meeting platform ourselves.
- Excellent for custom audio routing, server-side media handling, and nonstandard UX.
- Too low-level for the first skill prototype.

Tradeoffs:

- We must build signaling, auth, room semantics, UI, recording pipeline, transcription capture, moderation, and calendar integration.
- More engineering effort than LiveKit for similar agent-facing goals.

Verdict:

Powerful but too low-level for now. Consider only if LiveKit or Jitsi blocks a critical media requirement.

### 11. Janus

Janus is a general-purpose WebRTC server/gateway with plugins, including videoroom, SIP, streaming, and recording support. It is especially useful for bridging WebRTC with SIP, RTP, RTSP-like workflows, surveillance, broadcast, or specialized media pipelines.

Why it matters:

- Plugin architecture.
- Strong gateway story.
- Recording and RTP forwarding primitives exist.
- Good fit for nonstandard media interoperability.

Agentic meeting fit:

- Interesting if the agent needs to bridge meetings with SIP/PSTN or custom RTP/ASR infrastructure.
- Less ideal as a polished meeting app.
- Lower-level than Jitsi/BigBlueButton/LiveKit.

Tradeoffs:

- More media-server engineering required.
- The application layer is ours to design.

Verdict:

Best for specialized media gateway work, not for the first agentic meeting skill.

## Comparison Matrix

| Platform | Type | Self-host | Agent-native | Turnkey meeting UX | Live transcript path | Recording path | Best use |
|---|---|---:|---:|---:|---:|---:|---|
| Jitsi | Open-source meeting stack | Yes | Medium | High | Deployment-dependent | Jibri/local/file | Open self-hosted meetings with iframe control |
| LiveKit | Programmable RTC platform | Yes/cloud | High | Low/medium | Strong via agents/ASR integrations | Egress | Custom agent-first meetings |
| BigBlueButton | Open-source web conferencing | Yes | Medium | High | Medium | Strong | Structured classrooms/workshops |
| Daily | Hosted RTC platform | No | High | Medium | Strong | Strong | Fast hosted agent prototype |
| Zoom | Enterprise meeting platform | No | Medium | High | Strong post-meeting | Strong | Compatibility with existing Zoom meetings |
| Teams | Enterprise meeting platform | No | Medium | High | Strong post-meeting via Graph | Strong via Graph | Enterprise artifact workflows |
| Google Meet | Enterprise meeting platform | No | Low/medium | High | Strong post-meeting artifacts | Strong artifacts | Google Workspace integration |
| Element Call | Federated collaboration calling | Partial | Medium | Medium | Emerging | Emerging | Matrix-native persistent rooms |
| Galene | Lightweight WebRTC server | Yes | Low | Medium | DIY | Built-in disk recording | Minimal self-hosted experiments |
| MiroTalk SFU | Open-source meeting app | Yes | Medium | High | Needs verification | Advertised/built-in | Jitsi-like app on mediasoup |
| mediasoup | SFU toolkit | Yes | Medium/high if built | None | DIY | DIY | Full custom RTC stack |
| Janus | WebRTC gateway/server | Yes | Medium if built | Low | DIY | Stream/recording primitives | SIP/RTP/gateway-heavy systems |

## Product Implications

There are three different products hiding behind "meeting skill":

### A. Agent-managed meeting rooms

The agent creates rooms, calendar invites, agendas, policies, and post-meeting artifacts. It may not need raw media.

Best platforms:

- Jitsi
- BigBlueButton
- Google Meet
- Teams
- Zoom

### B. Agent participant in a live meeting

The agent joins, listens, speaks, tracks agenda, responds to commands, and emits live structured notes.

Best platforms:

- LiveKit
- Daily
- Jitsi via `lib-jitsi-meet` or iframe/headless browser
- Zoom/Teams/Meet via platform-specific bot approaches or browser automation

### C. Agent-native meeting runtime

The meeting app itself is designed around the agent: every participant, audio track, agenda item, decision, and artifact is structured.

Best platforms:

- LiveKit
- mediasoup, if maximum control is required
- Janus, if gateway/SIP/RTP is central

## Recommended Research Path

1. Keep Jitsi as the baseline because it is a complete self-hosted meeting app with iframe and low-level APIs.
2. Investigate LiveKit next because it is the strongest match for an agent-native runtime.
3. Investigate BigBlueButton if structured meetings, classroom-style facilitation, and recordings are important.
4. Treat Teams, Google Meet, and Zoom as compatibility adapters for existing meetings.
5. Treat mediasoup and Janus as lower-level escape hatches, not first prototypes.
6. Keep Galene and MiroTalk as lightweight/open-source alternatives worth testing after LiveKit/BBB.

## Suggested Next Documents

- `livekit-meeting-skill-research.md`: room lifecycle, token model, agents, Egress, Ingress, SIP, transcription, data channels.
- `bigbluebutton-meeting-skill-research.md`: API lifecycle, roles, recording, whiteboard/presentation, metadata, meeting artifacts.
- `enterprise-meeting-adapters.md`: Teams/Google Meet/Zoom scheduling, bot participation, transcript retrieval, consent and admin scopes.

