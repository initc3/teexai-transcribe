# Cues And Meeting Journey Notes

Date: 2026-06-03

This note imports the relevant ideas from `NOTES.md` and `user-journey-mapping/` into the agentic meeting skill research folder.

## Source Notes Observed

- [`NOTES.md`](../NOTES.md): working notes for the NEAR agentic transcript prototype, including the convergent blueprint from Hyprnote, Meetily, OpenWhispr, OpenGranola, and VoxTerm.
- [`user-journey-mapping/whiteboard-to-goku.md`](../user-journey-mapping/whiteboard-to-goku.md): the main meeting-to-transcript-to-action map.
- [`user-journey-mapping/last-night-map.md`](../user-journey-mapping/last-night-map.md): phase map of the Shape Rotator session, including explicit mentions of real-time cues.
- [`user-journey-mapping/README.md`](../user-journey-mapping/README.md): overview of the journey-mapping deliverables and source transcripts.

## Main Implication

The Jitsi/Hermes meeting skill should not just transcribe. It should detect and respond to meeting cues.

The notes point to a product model where a meeting is:

```text
Meeting idea -> Invite -> Meet/capture -> Transcript -> Redaction -> Summary -> Route -> Action
```

The agent's value lives in the middle and end of that chain:

- detecting live redaction and routing cues;
- preserving decisions and action items;
- composing different outputs for different recipients;
- staying quiet unless the cue is strong enough.

## Cue Types To Support

### 1. Transcription Quality Cues

From `NOTES.md`:

- silence and low-energy audio cause Whisper hallucinations;
- timer chunking cuts words and loses context;
- VAD-gated utterance segmentation is the right cue boundary;
- `avg_logprob` and `compression_ratio` from `verbose_json` are machine-checkable hallucination cues;
- source channel is a cue: mic = "you", tab/system = "them".

Skill implication:

- The meeting console should use VAD-gated segmentation, not a fixed 4s timer.
- The transcript stream should mark segments as `trusted`, `low_confidence`, or `dropped`.
- The agent should not act on low-confidence transcript text.

### 2. Redaction Cues

From `whiteboard-to-goku.md`:

- "let's redact this";
- "off the record";
- "don't put this in the notes";
- "between us";
- "this is confidential";
- sudden emergent sensitivity when a topic shifts;
- ACP/trust-boundary changes.

Skill implication:

- A live redaction cue should create a policy event, not merely delete text.
- The cue should affect downstream artifacts: summary, transcript excerpts, follow-ups, routing, and retention.
- Some policy is declared before the meeting; some is discovered during the meeting.

### 3. Preservation Cues

The whiteboard uses rectangles for positive-space artifacts: things worth preserving and routing.

Examples:

- "decision";
- "we decided";
- "the important thing is";
- "key point";
- "new information";
- "change since last time";
- "this affects ops";
- "send this to X";

Skill implication:

- The agent should treat preservation as first-class, not just redaction.
- It should build candidate artifacts: highlights, key info, new decisions, changes in state, action items.

### 4. Commitment Cues

From the journey map:

- candidate idea -> discussed -> accepted -> carried over;
- "yes, I'll do that";
- "I can take that";
- "let's make Alice owner";
- "due by Friday";
- "we agreed";
- "carry this over".

Skill implication:

- The acceptance moment is more important than the first mention of an action item.
- The agent should distinguish candidate actions from accepted commitments.
- Follow-up notes should not overstate weak commitments.

### 5. Agenda Drift And Facilitation Cues

From `last-night-map.md` and `NOTES.md`:

- agenda drift;
- reference pull-in;
- artifact generation;
- real-time cues such as "I say 'but' too much";
- topic shifts;
- open questions;
- tensions.

Skill implication:

- The agent should maintain a rolling conversation state: topic, open questions, tensions, desired outcome, current agenda item.
- It can surface gentle suggestions when the group is drifting, but should default to quiet.

### 6. Routing Cues

The meeting journey emphasizes that output is plural. A meeting does not produce one transcript for everyone. It produces tailored artifacts for recipients.

Routing cues include:

- "send this to the team";
- "ops needs this";
- "don't share this outside this room";
- "this is only for counsel";
- "Bob should see the action item, not the whole context";
- "public version";
- "participant version";
- "manager version".

Skill implication:

- The skill's output model should include recipient-specific artifacts.
- Redaction and routing are the same operation seen from negative and positive sides.

## OpenGranola Suggestion Cascade

`NOTES.md` calls OpenGranola the only truly agentic reference and identifies a five-stage suggestion cascade worth porting:

1. heuristic pre-filter;
2. rolling conversation-state JSON;
3. multi-query RAG over private notes;
4. abstention-first LLM gate with numeric thresholds;
5. grounded suggestion generation with citations.

This maps cleanly onto the Hermes/Jitsi skill.

For meetings, the cascade should become:

1. **Cue detector:** only consider acting when a transcript/event cue fires.
2. **State updater:** maintain topic, agenda item, commitments, sensitivities, open questions.
3. **Context retriever:** pull relevant notes/docs/past decisions.
4. **Abstention gate:** decide whether intervention is helpful now.
5. **Action generator:** produce a quiet suggestion, note, decision, redaction policy event, or routed artifact.

The abstention gate is critical. A meeting agent that interrupts constantly is worse than no agent.

## Updated Skill Design

The Hermes skill should have an internal cue/event stream:

```json
{
  "session_id": "string",
  "time": "string",
  "source": "jitsi_event | transcript | user_command | agent_inference",
  "type": "redaction | preservation | commitment | agenda_drift | routing | quality | participant",
  "text": "string",
  "confidence": 0.0,
  "policy_effect": "none | suppress | preserve | route | ask_user",
  "recipients": ["string"],
  "evidence": ["transcript segment ids"]
}
```

Meeting artifacts should be generated from this event stream, not directly from raw transcript text.

## Product Thesis Update

The first Hermes/Jitsi skill should be:

> A consent-aware meeting console that detects cues, turns them into structured events, and composes the right post-meeting artifacts for the right recipients.

That is more specific than "a Jitsi meeting skill" and closer to the strongest notes already in this repo.

