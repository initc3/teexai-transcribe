# Redaction effort — aligning to the meeting user-journey map

A planning note tying the realtime/Cue work and RedactBench back to
`user-journey-mapping/whiteboard-to-goku.md`, so we spend effort on the map's
most important problems rather than the easiest ones.

## The spine and where the value lives

Tina's 9 nodes: Conversation → Capture → Transcription → **Redaction** → Storage →
Retrieval → Agent → **Routing** → Action. The whiteboard's claim is that the value
concentrates in three places the deck draws as single boxes:

1. **The output is plural** (insight #1) — a meeting resolves to a *set* of per-recipient
   artifacts (permitted ∩ relevant), not one transcript + one summary. "That tailoring is
   the core." No existing tool does it.
2. **Policy is half-declared, half-discovered** (insight #2/#3) — predictable strikes
   (PII/confidential) are pre-loadable; **emergent strikes** ("let's strike that", sensitive-
   in-hindsight) surface live and "catching them is the harder problem… held, not yet solved."
3. **Provable redaction is the TEE wedge** (insight #5) — the differentiator is that the
   redaction + retention policy are *provable*, not that they're better than Otter.

Plus the gating thesis: **redaction is a discretion problem, not a PII problem** (insight #4),
the same discretion as recognizing an executable instruction in a transcript.

## Coverage map — what's built vs the priorities

| Map problem | Owner | Status | Gap |
|---|---|---|---|
| Discretion scoring (predictable strikes leak/keep) | **RedactBench** | Built + on CVM; ensemble judge; leak-gate + retention-floor | Single-audience contract only |
| **Plural output / fan-out** (insight #1, "the core") | — | **not covered** | RedactBench scores ONE notes artifact vs one audience; no per-recipient set |
| **Emergent-strike catching** (insight #3, "the hard one") | **Cue** | per-segment prototype; noisy | Wrong frame (per-segment); should catch live callouts + hindsight, measured by reliability |
| Provable redaction / attestation (insight #5) | RedactBench | scaffolded (`measurement: null`, CVM deploy) | real TDX quote + Verify (MVP-3) |
| Reliability of redaction over K | RedactBench | **decided-pending**: noise is in GENERATION, not the judge | change scoring to reliability-over-K before holdout |

## Cross-session synthesis (Cue × RedactBench)

Same teexai dataset, same discretion definition; they split at the **transcript→notes
artifact**:
- **Cue = capture → notes** (audio/realtime front-end). Natural home for the *emergent-strike
  catcher* — the map's hard, unsolved node.
- **RedactBench = notes → scorecard** (text/offline back-end). Owns leak/keep scoring,
  provability, the leaderboard.

Two independent confirmations of one fact:
- Cue: per-segment binary redaction with a cheap model swings precision/recall (.35/.89 ↔
  .40/.22) — can't isolate "this segment" from the sensitive neighborhood.
- RedactBench: the judge ensemble is *stable* (split_rate 0); the run-to-run wobble is the
  **redactor's generation** (leaks 4/5 inconsistently).

→ Both say: **measure the artifact, and measure reliability over K runs**, not a single
per-segment or single-shot decision. Don't duplicate the judge in Cue; reuse RedactBench's.

Model routing falls out: cheap **z.ai glm-4.5-flash** for realtime Cue catching, bigger
**near/glm-4.6** for the offline ensemble judge. Both in-TEE = an attested
"heard → kept/dropped → routed" chain.

## The two map-aligned gaps worth attacking

Current effort has gone deep on **discretion scoring of a single artifact** (RedactBench) and
on a **per-segment realtime prototype** (Cue) that the data says is the wrong frame. The map's
top two insights are the least covered:

- **A) Plural output / fan-out** (insight #1). Extend the strike contract from one `audience`
  to several recipients; score whether each recipient's view is both *permitted* (no leak) and
  *relevant* (kept what they need). This operationalizes the core thesis and is a natural
  RedactBench extension (the contract already carries an `audience` field).
- **B) Emergent-strike catching** (insight #3). Re-scope Cue from per-segment redactor to a
  *catcher*: detect the live "let's strike that" callout + sensitive-in-hindsight, emit strike
  markers, measure on reliability-over-K (matching RedactBench's finding). Feeds the contract
  that (A) then enforces.

Unifying arc: **Cue catches emergent strikes → strike contract → RedactBench scores the
per-recipient fan-out honoring it, in the CVM (provable).** That's the whole whiteboard,
end to end.
