# Cue Repo Integration Notes

Date: 2026-06-03

Source repo observed: `/home/amiller/projects/cue`

## Correction

Earlier "cue" notes in this folder used cue in the generic sense. The actual `cue` repo is a specific realtime agent harness, and it is highly relevant to the Jitsi/Hermes meeting skill.

The core idea from Cue:

> Cue is a silent realtime harness for agents you communicate with through the world.

It watches live observations, decides whether attention/action is warranted, and either calls a tool or explicitly emits `observe.pass`.

That is exactly the missing runtime layer for an agentic meeting skill.

## What Cue Provides

Cue's loop:

```text
continuous stream
  -> observation
  -> cue policy
  -> context packet
  -> agent/model/tool
  -> action or observe.pass
  -> recording + evals
```

Relevant abstractions:

- `Observation`: timestamped event with `type`, `payload`, `source`.
- `transcript.segment`: transcript observation shape with text, speaker, timestamps, confidence, words.
- `Cue`: wake-up reason, such as text hit, punctuation, speaker turn, idle stream, interval, or signal threshold.
- `CueHarness`: session state plus cues, programs, tools, and action dispatch.
- `LLMProvider`: chooses a tool call or `observe.pass`.
- `MappedActionTool`: maps model-selected tool calls into external actions.
- `observe.pass`: first-class "do nothing" decision, including reasons and pass spans.
- Transcript attention windows: recent speech can be highlighted without losing older context.
- Decision history: prior tool calls and pass spans are shown back to the model compactly.

Runtime/session endpoints from `AGENTS.md`:

- `GET /sessions/:id/agent`
- `GET /sessions/:id/state`
- `PATCH /sessions/:id/runtime`
- `POST /sessions/:id/observations`
- `WS /sessions/:id/ws`
- `WS /sessions/:id/events`
- `WS /sessions/:id/transcription`
- `WS /sessions/:id/vlm`

This is already shaped like the meeting console we were imagining.

## Relevant Examples

### `examples/meeting-red-alert`

This is the closest direct meeting prototype.

It defines `meeting.flag_unverified_claim`, which interrupts only when a speaker makes a concrete factual, metric, consensus, or risk claim that is likely false, underspecified, or needs immediate source checking.

The example uses:

- `PunctuationCue`
- a meeting-specific `LLMProvider`
- `MappedActionTool`
- action payload: `alert.show`
- cooldown: 60 seconds
- explicit `observe.pass` for non-actionable speech

This maps cleanly to meeting facilitation. Tools could be:

- `meeting.flag_unverified_claim`
- `meeting.capture_decision`
- `meeting.capture_action_item`
- `meeting.flag_redaction_request`
- `meeting.ask_clarifying_question`
- `meeting.route_artifact`

### `examples/but-coach`

This demo shows tight realtime coaching:

```text
browser MediaRecorder audio
  -> Cue /sessions/:id/transcription websocket
  -> Deepgram streaming transcription
  -> transcript.segment observation
  -> TextCue(["but"])
  -> model tool selection
  -> coach.interrupt_for_but action
```

The important lesson is not the word "but"; it is that Cue can run a highly constrained realtime intervention loop with cooldowns and tool eligibility.

For meetings, replace `TextCue(["but"])` with cues such as:

- "off the record"
- "let's redact"
- "we decided"
- "I'll take that"
- "send this to"
- "is that true?"

### `examples/voxterm-live`

This example already treats transcription as a provider and forwards finalized transcript segments. It uses `voxtermTranscriptionProvider`, `ManualCue`, and a tool that emits `voxterm.transcript`.

For our stack, the equivalent provider should be `teexaiTranscriptionProvider` or direct observation ingest from `teexai-transcribe`.

### `docs/prompt-creator-patterns.md`

This doc states the reusable loop clearly:

```text
observations
  -> rolling state
  -> cue
  -> attention window
  -> compact decision history
  -> prompt assembly
  -> eligible tool menu
  -> model selects tool or pass
  -> tool result actions
  -> raw trace and decision history updated
```

That should become the agentic meeting runtime model.

## How This Changes The Jitsi/Hermes Plan

Before reading Cue, the proposed design was:

```text
Jitsi meeting console
  -> teexai-transcribe
  -> Hermes skill tools
  -> summary/follow-up
```

After reading Cue, the better design is:

```text
Jitsi meeting console
  -> audio/transcript stream
  -> teexai-transcribe ASR/diarization
  -> Cue observations + cue policies
  -> Hermes-owned meeting actions/artifacts
```

Cue should own the realtime "should the agent act now?" layer.

Hermes should own the skill packaging, user-facing tools, and durable meeting workflow.

`teexai-transcribe` should own ASR, diarization, voiceprints, and transcript summarization primitives.

Jitsi should own room/media/convening.

## Proposed Split Of Responsibilities

### Jitsi

- room URL
- live meeting UI
- participant presence/events
- optional recording
- optional self-hosted auth/lobby

### `teexai-transcribe`

- audio decoding/transcoding
- Whisper/near.ai transcription
- final diarization
- voiceprint enrollment
- chat/summarization endpoint

### Cue

- session state
- transcript observation ingestion
- cue policies
- attention windows
- cooldowns
- eligible tool menus
- `observe.pass`
- action trace/evals/replay

### Hermes Skill

- user-facing skill instructions
- meeting lifecycle tools
- permission and consent prompts
- calendar/invite artifacts
- meeting console launch
- follow-up publication
- integration glue among Jitsi, Cue, and `teexai-transcribe`

## Concrete Integration Path

### Step 1: Observation Bridge

Convert `teexai-transcribe` output into Cue observations:

```json
{
  "type": "transcript.segment",
  "source": "teexai-transcribe",
  "payload": {
    "text": "We decided Alice owns the follow-up by Friday.",
    "speaker": "Andrew",
    "isFinal": true,
    "start": 123.4,
    "end": 128.9,
    "confidence": 0.91
  }
}
```

Send it to:

```text
POST /sessions/:id/observations
```

or stream to:

```text
WS /sessions/:id/ws
```

### Step 2: Meeting Cue Config

Create a Cue config like `examples/meeting-red-alert/server.config.ts` with programs for:

- redaction requests;
- action-item acceptance;
- decision capture;
- unverified factual claims;
- agenda drift;
- routing requests.

Each program should have strict cooldowns and conservative tool descriptions.

### Step 3: Meeting Actions

Map Cue tool calls into meeting actions:

```json
{ "type": "meeting.decision_captured", "payload": { "...": "..." } }
{ "type": "meeting.action_item_captured", "payload": { "...": "..." } }
{ "type": "meeting.redaction_policy_event", "payload": { "...": "..." } }
{ "type": "meeting.alert.show", "payload": { "...": "..." } }
{ "type": "meeting.followup_candidate", "payload": { "...": "..." } }
```

The Jitsi/Hermes console can subscribe to Cue events over:

```text
WS /sessions/:id/events
```

### Step 4: Console

The meeting console should display:

- Jitsi iframe;
- transcript;
- Cue decisions/actions;
- pass/action trace for debugging;
- consent state;
- agenda and current meeting goal;
- candidate artifacts.

### Step 5: Hermes Packaging

The Hermes skill should expose high-level tools, not Cue internals:

- `start_jitsi_meeting`
- `start_meeting_cue_session`
- `start_transcription`
- `capture_meeting_artifacts`
- `finalize_meeting`
- `draft_followup`

Internally it starts or connects to Cue and `teexai-transcribe`.

## Important Design Principle

The meeting agent should be quiet by default.

Cue already encodes that principle with `observe.pass`, cooldowns, tool eligibility, and decision history. We should reuse that rather than rebuilding a parallel realtime agent loop inside the Hermes skill.

## Immediate Recommendation

Do not make "Hermes Jitsi meeting skill" a monolith.

Build it as:

```text
Hermes skill package
  -> Jitsi room/session tools
  -> Cue meeting config
  -> teexai-transcribe provider/bridge
  -> browser meeting console
```

The first demo goal should be:

> Start a Jitsi meeting, transcribe it through `teexai-transcribe`, stream transcript segments into Cue, and let Cue produce conservative meeting actions such as decision capture, action-item capture, redaction requests, and unverified-claim alerts.

