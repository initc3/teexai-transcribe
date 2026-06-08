// Discreet meeting-notes redaction as a durable multi-pass workflow.
//   inventory -> [sensitivity | strategy | framing] (parallel) -> reconcile(audience) -> audit
// The framing pass is the false-positive guard; sensitivity/strategy pull the other way, so the
// passes are independent reviewers and `reconcile` resolves them for the stated recipient.
import { createSmithers, Sequence, Parallel } from "smithers-orchestrator";
import { z } from "zod";
import { redactAgent } from "./model.ts";

const inventorySchema = z.object({
  items: z.array(z.object({ id: z.string(), quote: z.string(), kind: z.string() })),
});
const verdictSchema = z.object({
  calls: z.array(z.object({
    id: z.string(),
    decision: z.enum(["keep", "drop", "generalize"]),
    reason: z.string(),
  })),
});
const noteSchema = z.object({ notes: z.string() });

const { Workflow, Task, smithers, outputs } = createSmithers({
  inventory: inventorySchema,
  verdict: verdictSchema,
  draft: noteSchema,
  output: noteSchema,
});

const JSON_ONLY = "\n\nReturn ONLY a JSON object, no prose, no markdown fences.";

const inventoryAgent = redactAgent(
  "You catalog a meeting transcript for an editor. List every item that MIGHT warrant discretion " +
  "(explicit 'keep this private' requests; anything sensitive in hindsight — health, finances, " +
  "allegations, credentials; names/details that could re-identify a protected person) AND every " +
  "benign-but-substantive fact a reader needs (decisions, numbers, owners, deadlines). One row per " +
  "item, with a short verbatim quote and a kind label. Do not decide keep/drop here — just inventory." + JSON_ONLY);

const lens = (name: string, charter: string) =>
  redactAgent(`You are the ${name} reviewer on a redaction panel. ${charter} For each inventory item ` +
    `return a call: decision is 'drop' (must not appear), 'generalize' (keep the substance but strip the ` +
    `sensitive specifics), or 'keep' (fine as-is). Judge only through your lens; the panel reconciles later.` + JSON_ONLY);

const sensitivityAgent = lens("Sensitivity",
  "You flag personally sensitive disclosure: PII, health, personal finances, credentials/secrets, and " +
  "anything identifying a complainant, accused, or whistleblower. A live secret (a key value, a diagnosis) " +
  "is drop; a generic version (rotated a credential, on medical leave) is generalize.");
const strategyAgent = lens("Strategy/deliberation",
  "You flag premature or strategic disclosure: undecided personnel actions, deals in progress, unproven " +
  "allegations, competitive secrets, and bad news not yet final. Deliberation drops; a settled decision keeps.");
const framingAgent = lens("Framing/context",
  "You are the FALSE-POSITIVE guard. A trigger word is a signal, never a verdict. Mark 'keep' when an item " +
  "is not a real disclosure: a meeting ABOUT redaction/security tooling using examples; quoted or reported " +
  "speech; a hypothetical, demo, or synthetic/placeholder datum; an in-character or rehearsal line; or already-" +
  "public information. Over-redaction is a failure on par with a leak — defend substance that is fine in context.");

const reconcileAgent = redactAgent(
  "You are the editor. Given the inventory, three reviewers' calls, and the intended AUDIENCE, write the " +
  "shareable notes for THAT recipient. Compose per-recipient: an item one audience may not see can be kept " +
  "for another (a manager readout may state a performance plan; internal eng may name a suspected root cause; " +
  "a public note states neither) — but hard secrets (a live credential value, a diagnosis, privileged strategy, " +
  "an individual's identity in an allegation) drop for everyone. Generalize rather than blank: replace a struck " +
  "item with the minimal shareable version that still lets the reader act. Keep all legitimate substance — " +
  "decisions, schedules, owners, deadlines, action items. Output markdown: a short summary, then '## Action " +
  "items' (owner - task - due) if any. No preamble, no note about omissions. Return {\"notes\": \"...\"}." + JSON_ONLY);

const auditAgent = redactAgent(
  "You audit a redaction draft against the source transcript for the stated audience. Read it twice: once " +
  "asking 'did anything this audience must not see survive, including by re-identification?' and once asking " +
  "'did the draft strip substance that was actually fine in context (a mention, quote, hypothetical, rehearsal, " +
  "or already-public fact)?'. Fix both kinds of error and return the corrected notes. Same output format: a " +
  "short summary then '## Action items' if any. Return {\"notes\": \"...\"}." + JSON_ONLY);

const block = (label: string, body: string) => `\n\n=== ${label} ===\n${body}`;

export default smithers((ctx) => {
  const transcript = ctx.input.transcript as string;
  const audience = (ctx.input.audience as string) ?? "the team";
  const inv = ctx.outputMaybe(outputs.inventory, { nodeId: "inventory" });
  const invJson = inv ? JSON.stringify(inv.items, null, 0) : "";
  const callsOf = (id: string) => {
    const v = ctx.outputMaybe(outputs.verdict, { nodeId: id });
    return v ? JSON.stringify(v.calls) : "";
  };
  const draft = ctx.outputMaybe(outputs.draft, { nodeId: "reconcile" })?.notes ?? "";

  return (
    <Workflow name="redact" cache>
      <Sequence>
        <Task id="inventory" output={outputs.inventory} agent={inventoryAgent}>
          {`Audience for the final notes: ${audience}.` + block("TRANSCRIPT", transcript)}
        </Task>

        <Parallel maxConcurrency={3}>
          <Task id="sensitivity" output={outputs.verdict} agent={sensitivityAgent}>
            {`Audience: ${audience}.` + block("INVENTORY", invJson) + block("TRANSCRIPT", transcript)}
          </Task>
          <Task id="strategy" output={outputs.verdict} agent={strategyAgent}>
            {`Audience: ${audience}.` + block("INVENTORY", invJson) + block("TRANSCRIPT", transcript)}
          </Task>
          <Task id="framing" output={outputs.verdict} agent={framingAgent}>
            {`Audience: ${audience}.` + block("INVENTORY", invJson) + block("TRANSCRIPT", transcript)}
          </Task>
        </Parallel>

        <Task id="reconcile" output={outputs.draft} agent={reconcileAgent}>
          {`Audience for these notes: ${audience}.` + block("INVENTORY", invJson) +
            block("SENSITIVITY CALLS", callsOf("sensitivity")) +
            block("STRATEGY CALLS", callsOf("strategy")) +
            block("FRAMING CALLS", callsOf("framing")) +
            block("TRANSCRIPT", transcript)}
        </Task>

        <Task id="audit" output={outputs.output} agent={auditAgent}>
          {`Audience for these notes: ${audience}.` + block("DRAFT NOTES", draft) + block("TRANSCRIPT", transcript)}
        </Task>
      </Sequence>
    </Workflow>
  );
});
