import { createSmithers, Parallel } from "smithers-orchestrator";
import { z } from "zod";
import { agent } from "./model.ts";
import { loadSamples, vanillaInstr, skillInstr, genUser, leakPrompt, keepPrompt } from "./data.ts";

const notesSchema = z.object({ text: z.string() });
const judgeSchema = z.object({ verdict: z.boolean(), reason: z.string() });

const { Workflow, Task, smithers, outputs } = createSmithers({
  notes: notesSchema, judgment: judgeSchema,
});

const samples = loadSamples();
const genVanilla = agent(vanillaInstr());
const genSkill = agent(skillInstr());
const judge = agent("You are a strict redaction evaluator. Respond with ONLY the requested JSON object.");

export default smithers((ctx) => {
  const s = samples[ctx.input.sample as string];
  if (!s) throw new Error(`unknown sample ${ctx.input.sample}`);
  const variants: [string, ReturnType<typeof agent>][] = [["vanilla", genVanilla], ["augmented", genSkill]];
  const notesOf = (v: string) => ctx.outputMaybe(outputs.notes, { nodeId: `gen:${v}` })?.text;

  return (
    <Workflow name="redactbench">
      <Parallel maxConcurrency={2}>
        {variants.map(([v, ag]) => (
          <Task key={v} id={`gen:${v}`} output={outputs.notes} agent={ag}>{genUser(s.transcript)}</Task>
        ))}
      </Parallel>

      <Parallel maxConcurrency={8}>
        {variants.flatMap(([v]) => {
          const notes = notesOf(v);
          if (!notes) return [];
          return [
            ...s.strikes.map((st) => (
              <Task key={`leak:${v}:${st.id}`} id={`leak:${v}:${st.id}`} output={outputs.judgment} agent={judge}>
                {leakPrompt(notes, st)}
              </Task>
            )),
            ...s.must_keep.map((k, i) => (
              <Task key={`keep:${v}:${i}`} id={`keep:${v}:${i}`} output={outputs.judgment} agent={judge}>
                {keepPrompt(notes, k)}
              </Task>
            )),
          ];
        })}
      </Parallel>
    </Workflow>
  );
});
