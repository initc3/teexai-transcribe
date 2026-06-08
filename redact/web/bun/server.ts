import { Database } from "bun:sqlite";
import { existsSync, readFileSync } from "node:fs";
import { loadSamples } from "./data.ts";

const PORT = Number(process.env.PORT ?? 8000);
const DIR = new URL(".", import.meta.url).pathname;
const DB = DIR + "smithers.db";
const HTML = readFileSync(DIR + "static/index.html", "utf8");
const samples = loadSamples();

const tok = (n: number) => Math.ceil(n / 4); // char/4 estimate, matching the transcribe HUD

function db() {
  return new Database(DB, { readonly: true });
}

async function startRun(sample: string): Promise<string> {
  const t0 = Date.now();
  Bun.spawn(["bunx", "smithers-orchestrator", "up", "redact.tsx", "--input",
    JSON.stringify({ sample }), "-c", "8"], { cwd: DIR, stdout: "inherit", stderr: "inherit", env: process.env });
  for (let i = 0; i < 60; i++) {
    if (existsSync(DB)) {
      const d = db();
      const r = d.query("select run_id from _smithers_runs where workflow_name='redactbench' and created_at_ms>=? order by created_at_ms desc limit 1").get(t0 - 1000) as any;
      d.close();
      if (r) return r.run_id;
    }
    await Bun.sleep(250);
  }
  throw new Error("run did not start");
}

function runState(runId: string) {
  if (!existsSync(DB)) return { status: "pending", nodes: [], tokensIn: 0, tokensOut: 0 };
  const d = db();
  const run = d.query("select status from _smithers_runs where run_id=?").get(runId) as any;
  const nodes = d.query("select node_id,state from _smithers_nodes where run_id=? order by node_id").all(runId) as any[];
  const attempts = d.query("select node_id,response_text,meta_json,started_at_ms,finished_at_ms from _smithers_attempts where run_id=?").all(runId) as any[];
  const judg = d.query("select node_id,verdict from judgment where run_id=?").all(runId) as any[];
  const notesRows = d.query("select node_id,text from notes where run_id=?").all(runId) as any[];
  d.close();

  const at: Record<string, any> = {};
  let tokensIn = 0, tokensOut = 0;
  for (const a of attempts) {
    let pl = 0; try { pl = (JSON.parse(a.meta_json)?.prompt || "").length; } catch {}
    const ol = (a.response_text || "").length;
    // enclave-network view: prompt tokens leave (out), completions return (in)
    at[a.node_id] = { out: tok(pl), in: tok(ol), done: !!a.finished_at_ms };
    if (a.finished_at_ms) { tokensOut += tok(pl); tokensIn += tok(ol); }
  }
  const notes: Record<string, string> = {};
  for (const r of notesRows) notes[r.node_id.replace("gen:", "")] = r.text;

  const card: Record<string, any> = {};
  for (const v of ["vanilla", "augmented"]) {
    const leaks = judg.filter((j) => j.node_id.startsWith(`leak:${v}:`) && j.verdict).map((j) => j.node_id.split(":")[2]);
    const keepN = judg.filter((j) => j.node_id.startsWith(`keep:${v}:`));
    card[v] = { verdict: leaks.length ? "LEAK" : "CLEAN", leaks, kept: keepN.filter((j) => j.verdict).length,
                n_keep: keepN.length, notes: notes[v] || "" };
  }

  return {
    status: run?.status || "pending", tokensIn, tokensOut,
    nodes: nodes.map((n) => ({ id: n.node_id, state: n.state, tok: at[n.node_id] || null })),
    scorecard: card,
  };
}

const json = (o: any) => new Response(JSON.stringify(o), { headers: { "content-type": "application/json" } });

Bun.serve({
  port: PORT,
  async fetch(req) {
    const url = new URL(req.url);
    if (url.pathname === "/") return new Response(HTML, { headers: { "content-type": "text/html" } });
    if (url.pathname === "/api/samples")
      return json(Object.values(samples).map((s) => ({ id: s.id, audience: s.audience, n_strikes: s.strikes.length, transcript: s.transcript })));
    if (url.pathname === "/api/run" && req.method === "POST") {
      const { sample } = await req.json();
      if (!samples[sample]) return json({ error: "unknown sample" });
      return json({ runId: await startRun(sample) });
    }
    const m = url.pathname.match(/^\/api\/run\/(.+)$/);
    if (m) return json(runState(m[1]));
    return new Response("not found", { status: 404 });
  },
});
console.log(`redactbench on :${PORT}`);
