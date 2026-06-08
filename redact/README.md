# discreet-meeting-notes

An audience-aware editorial-redaction skill, packaged with its own benchmark.

**What it does.** Turns a meeting transcript into shareable notes for a *specific recipient* —
honoring "keep this off the record" requests, dropping what's sensitive in hindsight (health,
finances, allegations, live credentials), and composing per-recipient (a manager readout may
state a performance plan that the public note must not). It treats redaction as **editorial
discretion, not pattern-matching**: a phone-number-shaped string or the phrase "off the record"
is a signal, never a verdict. Over-redaction is a failure on par with a leak.

**Why a benchmark ships with it.** The skill makes a falsifiable claim, so the package proves it.
`bench/` scores any redactor on two axes — **leakage** (did a struck item survive?) and
**retention** (did the substance survive, or did it over-redact?) — across 16 transcripts, and
reports the delta between a plain summarizer and the skill. This is the attestable-skill thesis:
the same workflow + judge can run in a TEE and emit a signed scorecard.

## Layout

```
skill/SKILL.md        canonical, harness-neutral source of truth (Anthropic frontmatter)
runtime/              the skill as a durable Smithers multi-pass workflow (redact.tsx) — see runtime/README.md
bench/                self-contained RedactBench: samples + scorer + run.sh
adapters/             thin per-harness wrappers (claude-code)
manifest.json         machine-readable descriptor
```

## Install (Claude Code)

```bash
cp -r adapters/claude-code/discreet-meeting-notes ~/.claude/skills/
```

The skill body is loaded as a system prompt; the model does the redaction in one pass. For the
durable, multi-pass, attestable form, use `runtime/` instead.

## Run the benchmark

```bash
cd bench
ZAI_API_KEY=sk-...  bash run.sh                      # all samples: plain summarizer vs the workflow
ARMS=vanilla,prompt,workflow  bash run.sh 11         # one sample, all three arms
```

Three arms: `vanilla` (no skill), `prompt` (SKILL.md as a single system prompt), `workflow`
(the Smithers multi-pass runtime). The workflow arm needs `bun` (it auto-installs `runtime/`).

## Notes

- Provider via `bench/llm.py` / `runtime/model.ts`: `zai` (z.ai GLM) by default, `near` for
  confidential TEE inference. Set `ZAI_API_KEY` / `NEAR_API_KEY`. **No keys are shipped.**
- Extend the dataset with `gen/` (the concept→plan→script+GT generation workflow).
