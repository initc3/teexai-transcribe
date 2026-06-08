// z.ai glm-4.6 agent (chat/completions, forced JSON) — same path as marketplace/pc/model.ts.
import { readFileSync } from "node:fs";

const BASE = "https://api.z.ai/api/coding/paas/v4";

function key(): string {
  if (process.env.ZAI_API_KEY) return process.env.ZAI_API_KEY;
  for (const line of readFileSync(new URL("../../.env", import.meta.url), "utf8").split("\n"))
    if (line.startsWith("ZAI_API_KEY=")) return line.slice("ZAI_API_KEY=".length).trim();
  throw new Error("ZAI_API_KEY not set (env or ../../.env)");
}

function promptOf(args: any): string {
  if (typeof args === "string") return args;
  const flat = (c: any) => (typeof c === "string" ? c : Array.isArray(c) ? c.map((p) => p.text ?? "").join("") : JSON.stringify(c));
  if (args?.messages?.length) return args.messages.map((m: any) => flat(m.content)).join("\n\n");
  if (args?.prompt != null) return flat(args.prompt);
  return JSON.stringify(args);
}

export function agent(instructions: string) {
  return {
    supportsNativeStructuredOutput: false,
    async generate(args: any) {
      const body = {
        model: "glm-4.6", temperature: 0,
        response_format: { type: "json_object" },
        messages: [
          { role: "system", content: instructions },
          { role: "user", content: promptOf(args) },
        ],
      };
      const headers = { Authorization: `Bearer ${key()}`, "Content-Type": "application/json" };
      for (let i = 0; ; i++) {
        const r = await fetch(`${BASE}/chat/completions`, { method: "POST", headers, body: JSON.stringify(body) });
        if ((r.status === 429 || r.status >= 500) && i < 5) {
          await new Promise((res) => setTimeout(res, 1000 * 2 ** i));
          continue;
        }
        if (!r.ok) throw new Error(`zai ${r.status}: ${(await r.text()).slice(0, 200)}`);
        const j: any = await r.json();
        const text = j.choices[0].message.content;
        return { text, content: text };
      }
    },
  };
}
