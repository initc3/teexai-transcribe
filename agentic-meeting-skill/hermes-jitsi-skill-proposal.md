# Hermes Jitsi Meeting Skill Proposal

Date: 2026-06-03

## Position

Packaging this as a Hermes agent skill is a good idea, as long as the first version is scoped as a meeting coordinator plus live transcript companion, not as a full autonomous WebRTC media stack.

The existing `teexai-transcribe` service changes the project shape. We already have a plausible ASR, diarization, speaker-enrollment, summarization, and transcript-agent backend. The Hermes skill should orchestrate meetings around that backend:

- create or select a Jitsi room;
- invite participants;
- prepare agenda/context;
- start a supervised meeting session;
- feed meeting audio/transcript into `teexai-transcribe`;
- maintain live meeting state;
- produce decisions, action items, and follow-ups;
- enforce explicit recording/transcription permissions.

## Skill Boundary

The skill should not initially try to implement Jitsi, WebRTC, or ASR internally. It should be a controller around four external surfaces:

1. Jitsi room/control surface.
2. Calendar/invite surface.
3. `teexai-transcribe` ASR/diarization/agent service.
4. Artifact store for agendas, transcripts, summaries, decisions, recordings, and follow-ups.

## First Useful Version

The first packaged version should support:

- `create_jitsi_room`: generate a high-entropy room URL on a configured Jitsi host.
- `schedule_meeting`: create invite payloads or calendar events with the Jitsi link and agenda.
- `prepare_meeting_context`: assemble agenda and context from user-provided notes/files.
- `start_meeting_console`: open or serve a small control page that embeds Jitsi and shows transcript/notes.
- `start_transcription`: explicitly begin audio capture/transcription after consent.
- `stop_transcription`: finalize transcript and run diarization.
- `summarize_meeting`: produce summary, decisions, action items, open questions, and parking-lot items.
- `publish_followup`: draft or send post-meeting follow-up after user approval.

This already creates a valuable agent workflow without requiring a headless Jitsi bot.

## Runtime Architecture

```text
Hermes agent
  |
  | tool calls
  v
Hermes meeting skill
  |
  |-- room/url/calendar tools
  |-- Jitsi iframe/control page
  |-- transcript session client
  |-- artifact store
  |
  v
teexai-transcribe
  |
  |-- /api/transcribe
  |-- /api/transcribe_diarized
  |-- /api/chat/stream
  |-- /api/agent
  |-- /api/enroll
```

The meeting console can initially be a browser page that has:

- a Jitsi iframe;
- transcript controls;
- consent/recording state;
- live transcript pane;
- agenda/notes pane;
- action-item/decision pane.

The console does not need to be beautiful first. It needs to make meeting state and consent state explicit.

## Tool Sketch

### `create_jitsi_room`

Inputs:

- `title`
- `host`
- `room_name_policy`: `random | slug-plus-random | fixed`
- `security`: lobby/password/JWT if available

Output:

- `room_url`
- `room_name`
- `host`
- `security_notes`

### `schedule_meeting`

Inputs:

- `title`
- `attendees`
- `time`
- `duration_minutes`
- `agenda`
- `room_url`

Output:

- calendar event draft or created event ID;
- invite text;
- meeting ID.

### `start_meeting_session`

Inputs:

- `meeting_id`
- `room_url`
- `transcription_policy`: `ask | start | never`
- `agent_mode`: `observer | facilitator | note_taker`

Output:

- console URL;
- session ID;
- current policy state.

### `ingest_audio_chunk`

Inputs:

- `session_id`
- audio bytes or browser-uploaded file
- chunk timestamp

Output:

- partial transcript text;
- model/provider metadata;
- confidence/diagnostics if available.

This may not be directly exposed to the top-level agent. It can be an internal console-to-skill endpoint.

### `finalize_transcript`

Inputs:

- `session_id`
- audio file or accumulated chunks

Output:

- diarized transcript segments;
- recognized speakers if voiceprints exist;
- final transcript artifact ID.

### `summarize_meeting`

Inputs:

- `session_id`
- summary style
- desired outputs

Output:

- summary;
- decisions;
- action items;
- open questions;
- follow-up draft.

## Agent Behavior During The Meeting

The agent can respond appropriately during a meeting only if it has a live event stream. That stream can combine:

- Jitsi iframe events: participants, role changes, recording/transcription status.
- Transcript chunks: partial speech-to-text from `teexai-transcribe`.
- User commands: chat/voice/manual controls.
- Agenda state: expected topics, time boxes, desired outcomes.

The first live behaviors should be conservative:

- capture explicit decisions;
- capture action items with owners;
- warn when agenda time is running out;
- answer "what have we decided so far?";
- draft follow-up notes but ask before sending.

Avoid having the agent interrupt the meeting automatically until the policy is clear.

## Audio Ingress Plan

Best first path:

1. Run a meeting console in the user's browser.
2. Embed Jitsi in that page.
3. Use browser capture/mic capture to feed `teexai-transcribe` chunks.
4. At the end, finalize with diarization.

Better later path:

1. Agent joins Jitsi as a visible participant.
2. It captures/subscribes to remote audio tracks.
3. It streams audio to `teexai-transcribe`.
4. It posts transcript/status messages back to the meeting.

Recording-first fallback:

1. Record with Jitsi/Jibri/local browser capture.
2. Send file to `/api/transcribe_diarized`.
3. Produce post-meeting artifacts.

## Permission Model

The skill should ask explicitly before:

- inviting participants;
- starting transcription;
- starting recording;
- enrolling a speaker voiceprint;
- sending follow-up notes;
- publishing a transcript;
- sharing recordings/transcripts outside the participant group.

Standing policies can reduce prompts later, but the first version should keep the consent boundary obvious.

Suggested scopes:

- `meeting:create_room`
- `meeting:schedule`
- `meeting:invite`
- `meeting:start_transcription`
- `meeting:start_recording`
- `meeting:read_transcript`
- `meeting:enroll_voiceprint`
- `meeting:publish_summary`
- `meeting:send_followup`

## What Makes This A Good Hermes Skill

This is a good skill because it has clear procedural knowledge and state:

- how to create a meeting;
- how to prepare context;
- how to enforce consent;
- how to watch/ingest the meeting;
- how to turn transcript into outcomes;
- how to publish artifacts.

It also has useful fallback paths. If live Jitsi integration fails, the skill can still operate from an uploaded recording or pasted transcript. If transcription is unavailable, it can still schedule and prepare the meeting.

## First Build Slice

Build a thin package with:

1. `SKILL.md` instructions for Hermes/Codex-style agents.
2. `tools/room.py` or equivalent: generate Jitsi room URLs.
3. `tools/session.py`: create session records and artifact folders.
4. `console/`: iframe + transcription-control page adapted from `teexai-transcribe/static/index.html`.
5. `client/transcribe.py`: wrapper around `teexai-transcribe` endpoints.
6. `examples/`: one scripted meeting flow from schedule to summary.

Do not implement OAuth calendar integration first. Start with generated `.ics` or invite text. Real calendar APIs can come after the room/session/transcript loop is proven.

## Open Questions

- What exact package format does Hermes expect for skills?
- Does Hermes allow serving a local web console from a skill?
- Can Hermes expose binary upload/streaming endpoints, or should the console talk directly to `teexai-transcribe`?
- Should the Jitsi room be public `meet.jit.si`, self-hosted Jitsi, or configurable?
- Is the first agent mode a silent note-taker, a chat facilitator, or a voice participant?

## Recommendation

Proceed. Package the first version as a Hermes skill that wraps Jitsi room management plus `teexai-transcribe` meeting intelligence. Keep the WebRTC bot work out of v0. The goal for v0 should be:

> "Ask my agent to set up a meeting, open the meeting console, transcribe the session with consent, and produce useful follow-up artifacts."

That is realistic with the current codebase.

