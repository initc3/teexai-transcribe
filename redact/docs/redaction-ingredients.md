# The ingredients of redaction — a layered model + eval scenarios

Redaction is not one capability; it's a stack. Each layer is an *ingredient* with its own
failure mode. Today RedactBench collapses the middle layers into a single leak/keep verdict
on one artifact, single-shot. This note names the layers and the **scenario** that isolates
each, so the eval can grow by ingredient instead of by sample count.

Companion to `investigation-skills-tee/REDACTBENCH.md` (the task + attested harness) and
`user-journey-mapping/whiteboard-to-goku.md` (the source insights, cited as #n below).

## The five layers

```
L5  ASSURE    reliable over K runs + provable (attested)        ← our generation-noise finding
L4  COMPOSE   the right per-recipient artifact (permitted ∩ relevant)   ← insight #1 "the core"
L3  DECIDE    is suppression CORRECT here? (emotional=wrong, strategic-undecided=right)  ← #7
L2  CLASSIFY  which reason family? sensitive-data / strategic / noise   ← #6
L1  DETECT    is there an obligation, and where from? explicit / hindsight / policy   ← #2,#3
```

A redactor can pass a lower layer and fail a higher one: catch every strike (L1) yet send the
same notes to everyone (fails L4); drop all sensitive content (L2) yet bury the bad news ops
needs (fails L3). The bench should score each layer, not a blended pass/fail.

## Layer by layer — what it is, what's covered, the scenario to add

### L1 — DETECT (where the obligation comes from)
- **explicit** strike — a live callout creates the duty ("between us", "don't tell my manager").
  Emergent; knowable only from the utterance. *Covered* (`type:explicit`, every sample).
- **hindsight** strike — sensitive though nobody flagged it; needs world-knowledge/discretion.
  *Covered* (`type:hindsight`).
- **policy-implied** — PII/confidential by standing policy, pre-loadable. *Implicit in hindsight; not separately tagged.*
- **NEW scenario — distractor / false trigger.** A phrase that *looks* like an explicit strike
  but isn't a redaction request ("just between us — great work"), or sensitive-sounding content
  that's actually public. The redactor must NOT drop it. Measures L1 *precision* (over-trigger),
  which nothing tests today. Tag: `decoy:true` on a pseudo-strike whose correct action is keep.
- **NEW scenario — ACP trajectory** (insight #3 sub). Privilege is held, a third party joins at
  time T, everything privileged-before-T must not reach them. Monotonic, stateful — a different
  shape from per-strike classification. Tag: a `boundary_event` at T; strikes scoped by time.

### L2 — CLASSIFY (reason family decides treatment)
Three families (insight #6): **sensitive-data** (PII/health/finance/identifiers/ACP — drop hard,
mostly predictable), **strategic** (premature-naming, pay-equity, bad-news-undecided — context-
dependent), **noise** (jokes/off-topic/background — low-stakes tidy-up). *Themes encode families
but there's no `family` tag, and **no noise strikes exist at all**.*
- **NEW: add `family` to every strike** so the scorecard can report treatment-appropriateness
  per family (e.g. did it drop strategic content for the wrong reason).
- **NEW scenario — noise.** Off-topic banter that shouldn't clutter notes but is not a leak if it
  survives. Scored on a separate *tidiness* axis, NOT the leak gate — tests that the redactor
  distinguishes "drop because noise" from "drop because sensitive."

### L3 — DECIDE (is the suppression correct?)
The hardest, and the one the retention *floor* only half-guards. Floor catches blanket over-
redaction; it does NOT catch **targeted wrong suppression** — hiding something that SHOULD be
kept because it's uncomfortable (insight #7: emotional suppression is a mistake; strategic-
undecided suppression is correct). Sample 02 is the canonical case: the severance number MUST
stay (ops needs it) but the early options menu must not leak.
- **NEW scenario — adversarial keep.** A `must_keep` that is emotionally charged or embarrassing
  ("we missed the deadline, it's on me") where a coward redactor wrongly drops it. Makes
  retention adversarial, not just a floor. Tag: `must_keep` entries gain `kind: operational | emotional-but-needed`.
- This is also where **discretion = executable recognition** (insight #4) bites: deciding a span
  matters is the same skill as recognizing an instruction to act on.

### L4 — COMPOSE (the plural output — "the core")
Insight #1: the deliverable is a *set* of per-recipient views, each **permitted** (trust: may see)
∩ **relevant** (routing: cares about). *Not covered — single `audience` per sample.*
- **NEW scenario — multi-recipient.** One transcript, ≥2 recipient contracts (ops-team / public
  all-hands / the affected individual), each with its own strikes + must_keep. Score per recipient:
  leak (permitted) AND relevance (did the right slice arrive). Squiggle removes, rectangle routes.
  Tag: replace `audience` with `recipients: [{ id, audience, strikes, must_keep }]`.

### L5 — ASSURE (reliable + provable)
Our cross-session finding: the judge ensemble is stable; the **redactor's generation** wobbles
(leaks 4/5). And insight #5: provability is the TEE wedge.
- **Scoring protocol, not data:** run the redactor K times per scenario, report **pass-rate /
  leak-distribution** (= redaction *reliability*; clean 4/5 is dangerous). Then attest config+data+score.
- This subsumes the pending RedactBench "reliability-over-K" decision.

## How the eval extends (concrete)

Contract changes (backward-compatible — old samples keep working):
- strike gains `family: sensitive-data | strategic | noise` and optional `decoy: true`.
- `must_keep` entries gain `kind: operational | emotional-but-needed`.
- `audience` generalizes to `recipients: [{ id, audience, strikes, must_keep }]` (single-recipient
  = today's shape).
- optional `boundary_event: { t, kind: "third-party-joined" }` for ACP-trajectory samples.

Scorecard gains per-layer sub-scores: L1 explicit-honor / hindsight-discretion / **false-trigger**
rates; L2 per-family treatment; L3 **adversarial-keep** retention; L4 per-recipient leak + relevance;
L5 K-run pass-rate + variance. The single clean-AND-useful gate stays on top.

Each new scenario is a small set of samples (or tags on existing ones) that holds every layer easy
except the one under test — so a score localizes the failure to an ingredient.
