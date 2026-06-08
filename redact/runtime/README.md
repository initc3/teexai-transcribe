# discreet-meeting-notes — runtime

The skill as a durable [Smithers](https://smithers.sh) multi-pass workflow. One transcript +
the intended audience in, redacted notes out.

```
inventory ── catalog every item that might warrant discretion + every fact a reader needs
   │
   ├── sensitivity   (PII / health / finance / credentials / privilege)
   ├── strategy      (undecided decisions, deals, unproven claims, premature bad news)
   └── framing       (the FALSE-POSITIVE guard: mention vs use, quote, hypothetical, rehearsal, public)
   │
reconcile(audience) ── compose for THIS recipient; hard secrets drop for everyone
   │
audit ── re-scan for survivors AND for over-redaction; emit the final note
```

The three perspectives run in parallel and pull in opposite directions — sensitivity/strategy
want to cut, framing defends substance. `reconcile` resolves them for the stated audience;
`audit` is two-sided so over-redaction is caught like a leak. Each pass is a separate, durable,
attestable agent (z.ai glm-4.6, forced JSON, thinking disabled — the passes are the reasoning).

## Run

```bash
bun install
export ZAI_API_KEY=sk-...
bun run.ts '{"transcript":"NAME: ...","audience":"public_channel"}'
```

Prints the redacted notes to stdout. State persists to `smithers.db` (crash-safe, resumable).
Swap the provider in `model.ts` (e.g. near.ai for confidential TEE inference).
