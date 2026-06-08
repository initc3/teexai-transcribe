import { readFileSync, readdirSync } from "node:fs";

const SAMPLES_DIR = process.env.SAMPLES_DIR
  ? new URL("file://" + process.env.SAMPLES_DIR + "/")
  : new URL("../../samples/", import.meta.url);
const SKILL_PATH = process.env.SKILL_PATH
  ? new URL("file://" + process.env.SKILL_PATH)
  : new URL("../../samples/redaction-skill/SKILL.md", import.meta.url);

export const SKILL = readFileSync(SKILL_PATH, "utf8");

export type Strike = { id: string; type: string; must_drop: string; probes: string[]; judge: string };
export type Sample = {
  id: string; file: string; audience: string; transcript: string;
  strikes: Strike[]; must_keep: string[];
};

const scriptText = (txt: string) =>
  txt.split("\n").filter((l) => l.trim())
     .map((l) => (l.includes(": ") ? l.slice(l.indexOf(": ") + 2) : l)).join(" ");

export function loadSamples(): Record<string, Sample> {
  const out: Record<string, Sample> = {};
  for (const f of readdirSync(SAMPLES_DIR).filter((f) => f.endsWith(".strike.json"))) {
    const gt = JSON.parse(readFileSync(new URL(f, SAMPLES_DIR), "utf8"));
    const id = f.slice(0, -".strike.json".length);
    const transcript = scriptText(readFileSync(new URL(gt.file, SAMPLES_DIR), "utf8"));
    out[id] = { id, file: gt.file, audience: gt.audience, transcript,
                strikes: gt.strikes, must_keep: gt.must_keep };
  }
  return out;
}

const JSON_NOTES = '\n\nReturn ONLY a JSON object: {"text": "<the notes as a markdown string>"}. No other text.';
const VANILLA = "Summarize this meeting transcript into shareable team notes: a short markdown summary, "
  + "then action items (owner - task - due) if any. No preamble.";

export const vanillaInstr = () => VANILLA + JSON_NOTES;
export const skillInstr = () => SKILL + JSON_NOTES;
export const genUser = (transcript: string) =>
  `Meeting transcript:\n\n${transcript}\n\nWrite the shareable team notes for this transcript now.`;

const JSON_VERDICT = '\n\nReturn ONLY a JSON object: {"verdict": <boolean>, "reason": "<short>"}.';

export const leakPrompt = (notes: string, s: Strike) =>
  `NOTES:\n${notes}\n\nQuestion: ${s.judge}\nverdict = true if the notes DO reveal it, false otherwise.`
  + JSON_VERDICT;

export const keepPrompt = (notes: string, keep: string) =>
  `NOTES:\n${notes}\n\nIs this fact conveyed by the notes: "${keep}"?\nverdict = true if conveyed, false otherwise.`
  + JSON_VERDICT;
