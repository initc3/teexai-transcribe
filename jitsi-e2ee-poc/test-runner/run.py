import os, re, sys, time, requests

PHRASE = os.environ["PHRASE"]
SECS = int(os.environ.get("MEET_SECONDS", "40"))
STOP = {"the", "a", "an", "over", "of", "and"}


def toks(s):
    return set(re.findall(r"[a-z]+", s.lower()))


CONTENT = toks(PHRASE) - STOP


def overlap(text):
    t = toks(text)
    return len(CONTENT & t) / max(1, len(CONTENT))


print(f"[test] content words: {sorted(CONTENT)}", flush=True)
print(f"[test] running meeting for {SECS}s...", flush=True)
time.sleep(SECS)

r = requests.get("http://asr:8000/results", timeout=180).json()
lis = r.get("listener", {})
eve = r.get("eavesdropper", {})
ol_l, ol_e = overlap(lis.get("text", "")), overlap(eve.get("text", ""))

print(f"[test] listener     samples={lis.get('samples')} overlap={ol_l:.2f} text={lis.get('text')!r}", flush=True)
print(f"[test] eavesdropper samples={eve.get('samples')} overlap={ol_e:.2f} text={eve.get('text')!r}", flush=True)

keyed_can_read = ol_l >= 0.5
keyless_cannot_read = ol_e < 0.3
ok = keyed_can_read and keyless_cannot_read
print(f"[test] keyed listener can transcribe : {keyed_can_read}", flush=True)
print(f"[test] keyless eavesdropper is blind  : {keyless_cannot_read}", flush=True)
print(f"[test] RESULT: {'PASS' if ok else 'FAIL'} — E2EE {'holds: only the keyed participant reads audio' if ok else 'assertion failed'}", flush=True)
sys.exit(0 if ok else 1)
