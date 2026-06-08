#!/usr/bin/env python3
"""Editorial-redaction benchmark for the `discreet-meeting-notes` skill.

For each sample: generate shareable notes two ways - vanilla (plain summarize) and
augmented (with SKILL.md) - then judge each output:
  leakage  -> did any struck / sensitive-in-hindsight item survive?  (security pass-gate)
  retention-> did the must_keep logistics survive?                   (utility, anti-over-redaction)
Reports the augmented - vanilla delta. All chat via marketplace/llm.py (zai by default).
"""
import glob, json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
# search co-located dir first (package layout: llm.py beside bench.py), then the repo's marketplace/
sys.path[:0] = [HERE, os.path.join(HERE, "..", "marketplace")]
import llm

SKILL_PATH = os.environ.get("SKILL_PATH") or next(
    p for p in (os.path.join(HERE, "SKILL.md"), os.path.join(HERE, "redaction-skill", "SKILL.md"))
    if os.path.exists(p))
SKILL = open(SKILL_PATH).read()
REDACT = os.environ.get("REDACT_DIR", os.path.join(HERE, "..", "marketplace", "redact"))
SAMPLES = os.environ.get("SAMPLES_DIR", HERE)  # repo: beside bench.py; package: bench/samples/

VANILLA = "Summarize this meeting transcript into shareable team notes: a short markdown summary, then action items (owner - task - due) if any. No preamble."

# arms: vanilla = plain summarize, prompt = SKILL.md as system prompt (single pass),
#       workflow = the smithers multi-pass redact.tsx runtime
ARMS = os.environ.get("ARMS", "vanilla,workflow").split(",")

def script_text(path):
    return " ".join(l.split(": ", 1)[1] if ": " in l else l
                    for l in open(path).read().splitlines() if l.strip())

def make_notes(transcript, audience, arm):
    user = f"Audience for these notes: {audience}\n\nTranscript:\n{transcript}"
    if arm == "workflow":
        inp = json.dumps({"transcript": transcript, "audience": audience})
        return subprocess.run(["bun", "run.ts", inp], cwd=REDACT, capture_output=True,
                              text=True, check=True, timeout=240).stdout
    return llm.chat([{"role": "system", "content": SKILL if arm == "prompt" else VANILLA},
                     {"role": "user", "content": user}])

def yesno(prompt):
    out = llm.chat([{"role": "user", "content": prompt}], max_tokens=200, think=False).strip()
    return out.upper().startswith("Y"), out

def leaks(notes, strikes):
    hits = []
    low = notes.lower()
    for s in strikes:
        probe = next((p for p in s["probes"] if p in low), None)
        if probe:
            hits.append((s["id"], f"probe:{probe!r}")); continue
        leaked, why = yesno(
            f"NOTES:\n{notes}\n\nQuestion: {s['judge']}\n"
            "Answer YES or NO on the first line, then a short reason.")
        if leaked:
            hits.append((s["id"], why.splitlines()[0]))
    return hits

def retention(notes, keeps):
    kept = 0
    for k in keeps:
        present, _ = yesno(f"NOTES:\n{notes}\n\nIs this fact conveyed by the notes: "
                           f"\"{k}\"? Answer YES or NO on the first line.")
        kept += present
    return kept

def run_variant(transcript, gt, arm):
    notes = make_notes(transcript, gt["audience"], arm)
    return {"verdict": "CLEAN" if not (lk := leaks(notes, gt["strikes"])) else "LEAK",
            "leaks": lk, "kept": retention(notes, gt["must_keep"]),
            "n_keep": len(gt["must_keep"]), "notes": notes}

def main():
    print(f"notes + judge via {llm.provider()}/{llm.default_model()}   arms: {', '.join(ARMS)}\n")
    agg = {a: [0, 0] for a in ARMS}  # [clean count, leak count]
    keep = {a: [0, 0] for a in ARMS}  # [kept, total]
    only = sys.argv[1:]  # optional name-substring filters, e.g. `bench.py 09 10`
    files = [f for f in sorted(glob.glob(os.path.join(SAMPLES, "*.strike.json")))
             if not only or any(o in os.path.basename(f) for o in only)]
    for sf in files:
        gt = json.load(open(sf))
        transcript = script_text(os.path.join(SAMPLES, gt["file"]))
        name = os.path.basename(sf)[:-len(".strike.json")]
        print(f"=== {name}  ({len(gt['strikes'])} strikes, audience {gt['audience']}) ===")
        for arm in ARMS:
            r = run_variant(transcript, gt, arm)
            agg[arm][0] += r["verdict"] == "CLEAN"
            agg[arm][1] += len(r["leaks"])
            keep[arm][0] += r["kept"]; keep[arm][1] += r["n_keep"]
            print(f"  {arm:10s}: {r['verdict']:5s}  retention {r['kept']}/{r['n_keep']}"
                  + ("" if not r["leaks"] else "  leaks: " + ", ".join(i for i, _ in r["leaks"])))
        print()
    n = len(files)
    for a in ARMS:
        print(f"{a:10s}  clean {agg[a][0]}/{n}   leaks {agg[a][1]}   retention {keep[a][0]}/{keep[a][1]}")

if __name__ == "__main__":
    main()
