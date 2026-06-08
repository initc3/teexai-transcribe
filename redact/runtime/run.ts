// Run the redact workflow once and print the final notes to stdout.
//   bun run.ts '{"transcript":"...","audience":"public_channel"}'
import { runWorkflow } from "smithers-orchestrator";
import { Effect } from "effect";
import { Database } from "bun:sqlite";
import workflow from "./redact.tsx";

const input = JSON.parse(process.argv[2]);
const result = await Effect.runPromise(runWorkflow(workflow, { input }));
if (result.status !== "finished") throw new Error(`workflow ${result.status}: ${JSON.stringify(result.error)}`);
const db = new Database(new URL("./smithers.db", import.meta.url).pathname, { readonly: true });
const row = db.query("select notes from output where run_id=? order by iteration desc limit 1").get(result.runId) as { notes: string };
process.stdout.write(row.notes);
process.exit(0);  // runWorkflow leaves the Effect runtime/DB handle alive; exit explicitly so callers don't block
