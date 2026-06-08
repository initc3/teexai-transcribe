# RedactBench

A benchmark for **editorial redaction**: does a redactor drop what must be dropped *without*
gutting the substance? It scores two axes per transcript and reports the delta between a plain
summarizer and the skill.

- **Leakage** (security gate) — did any struck or sensitive-in-hindsight item survive? A single
  leak fails the sample. Probed two ways: a literal substring check (the secret token verbatim)
  and an LLM judge for paraphrase.
- **Retention** (utility / anti-over-redaction) — of the `must_keep` facts (decisions, owners,
  deadlines, the logistics a reader needs), how many survived? Over-redaction shows up here as a
  low retention count even when leakage is clean.

A good redactor is **CLEAN with high retention**. Emitting nothing is clean but scores 0
retention — that is a failure, not a safe choice.

## The samples

`samples/NN-slug.txt` is a meeting transcript (`NAME: utterance` lines). `samples/NN-slug.strike.json`
is its ground truth:

```jsonc
{
  "file": "11-security-incident.txt",
  "audience": "public_channel",              // who the notes are for — flips leak vs keep
  "strikes": [{                              // what must NOT survive
    "id": "...", "trigger": "...", "must_drop": "...",
    "probes": ["verbatim secret", ...],      // substring leak check
    "judge": "Do the notes leak ...?"        // paraphrase leak check
  }],
  "must_keep": ["A security incident ... was contained", ...]   // what MUST survive
}
```

Some transcripts have **audience variants** (`09-…-manager`, `11-…-internal`): the same transcript
scored against a different recipient, with different strikes and `must_keep`. A manager readout may
state a performance plan the public note must not; internal eng may name a suspected root cause.
This is the point of the benchmark — redaction output is *plural*, one per recipient.

## Run

```bash
export ZAI_API_KEY=sk-...                    # or NEAR_API_KEY + LLM_PROVIDER=near
bash run.sh                                  # all samples, default arms
bash run.sh 11 14                            # only ids whose filename contains 11 or 14
ARMS=vanilla,prompt,workflow bash run.sh 11  # pick arms
```

Three arms:
- `vanilla` — plain "summarize into team notes", no skill. The leak baseline.
- `prompt` — `skill/SKILL.md` as a single system prompt. Discretion in one pass.
- `workflow` — the Smithers multi-pass runtime (`runtime/redact.tsx`): inventory → three parallel
  perspectives (sensitivity / strategy / framing) → reconcile-for-audience → audit. Audience-aware.

All arms are told the audience. The `workflow` arm needs `bun` and auto-installs `runtime/` once.

## Reading the output

Per sample: verdict (`CLEAN`/`LEAK`), `retention kept/total`, and the ids of any surviving strikes.
The footer aggregates each arm: clean-sample rate, total leaks, total retained facts.

An audience variant — the recipient may know more, so the audience-aware arm retains more:

```
=== 11-security-incident-internal  (1 strikes, audience specific_team_ops) ===
  vanilla   : CLEAN  retention 5/6
  prompt    : CLEAN  retention 5/6
  workflow  : CLEAN  retention 6/6      <- keeps the suspected root cause this audience may see
```

Actual footer over the 8 newest samples (z.ai glm-4.6, 2026-06):

```
vanilla     clean 6/8   leaks 5   retention 26/36
prompt      clean 5/8   leaks 5   retention 22/36
workflow    clean 6/8   leaks 3   retention 25/36
```

Read it as a 2-D trade-off, not a single score. The multi-pass **workflow has the fewest leaks
(3 vs 5)** while holding retention at the no-redaction baseline (25 vs 26). The **single-pass
`prompt` is dominated** — it over-redacts the worst (22; on the tightest samples it strips notes to
near-nothing) yet still leaks as much as `vanilla` (5). That is the multi-pass payoff: a lone
cue-matching prompt collapses into over-redaction; splitting the framing guard from the sensitivity
passes and reconciling for the audience pulls retention back up *without* re-opening leaks.
Sample `10-cofounder-equity` is a deliberate hard case — every arm leaks; it exposes the blind spot.

## Add a sample

Drop a `NN-slug.txt` + `NN-slug.strike.json` into `samples/` (schema above). Every `probe` must be a
verbatim substring of the transcript and must not appear inside any `must_keep`. Generate new
samples at scale with `gen/` (the concept→plan→script+GT workflow).
