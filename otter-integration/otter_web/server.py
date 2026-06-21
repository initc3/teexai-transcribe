#!/usr/bin/env python3
"""Local web app: follow a live Otter meeting (transcript + screenshots) with a
"what were we talking about?" button that also reads the current slide.

Runs entirely on your machine. Reuses the Chrome otter.ai session (browser_cookie3)
to poll the live transcript and screenshare frames, and your NEAR AI Cloud key to
summarize on demand. Frames live on api.aisense.com (cookie-auth), so the server
proxies them via /frame. When a recent slide exists, the recap goes to Qwen3-VL so
it accounts for what's on screen; otherwise a fast text model.

  python3 server.py            # serves on http://localhost:8137
"""
import base64, hashlib, hmac, json, os, re, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import requests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from otter_session import open_session
from otter_web import matrix

HERE = Path(__file__).parent
PORT = int(os.environ.get("PORT", 8137))
OTTER = "https://otter.ai/forward/api/v1/"
NEAR_URL = "https://cloud-api.near.ai/v1/chat/completions"
TEXT_MODEL = os.environ.get("NEAR_MODEL", "deepseek-ai/DeepSeek-V4-Flash")
VL_MODEL = os.environ.get("NEAR_VL_MODEL", "google/gemini-2.5-flash")


NEAR_KEY = os.environ.get("NEAR_KEY") or os.environ["NEAR_API_KEY"]
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8137")

OWNER_TOKEN = os.environ.get("OWNER_TOKEN")
if not OWNER_TOKEN:
    print("WARNING: OWNER_TOKEN unset — auth disabled, everyone treated as owner (local dev only)", file=sys.stderr)


def share_sig(otid):
    return hmac.new(OWNER_TOKEN.encode(), otid.encode(), hashlib.sha256).hexdigest()[:16]


def share_url(otid):
    return f"{BASE_URL}/#view={otid}.{share_sig(otid)}"

DATA = Path(os.environ.get("OTTER_OUT", "/data/otter" if os.path.isdir("/data") else str(HERE / "data")))
STATE_DIR = DATA / "state"
LIVE_DIR = DATA / "live"


_SESSION = {"s": None, "t": 0.0}
def otter():
    # reuse the session (open_session does a /user round-trip each call); cookie is static
    now = time.time()
    if _SESSION["s"] is None or now - _SESSION["t"] > 300:
        _SESSION["s"] = open_session(); _SESSION["t"] = now
    return _SESSION["s"]


def live_speech(s):
    speeches = s.get(OTTER + "speeches", params={"userid": s.uid, "page_size": 20, "source": "owned"},
                     timeout=40).json()["speeches"]
    live = [x for x in speeches if x.get("live_status") == "live"]
    return live[0] if live else None


_LIVE = {"sp": None, "t": 0.0}
def live_speech_cached(s, ttl=8):
    # the live-status check (speeches list) is the slow per-request cost; cache it briefly so the
    # dashboard's /conversations + /graph polls (and otter_wake) don't each re-hit the Otter API
    now = time.time()
    if now - _LIVE["t"] >= ttl:
        _LIVE.update(sp=live_speech(s), t=now)
    return _LIVE["sp"]


def proxied(url):
    return "/frame?u=" + base64.urlsafe_b64encode(url.encode()).decode()


def live_state(after):
    s = otter()
    sp = live_speech_cached(s)
    if not sp:
        return {"live": False}
    d = s.get(OTTER + "speech", params={"userid": s.uid, "otid": sp["otid"]}, timeout=40).json()["speech"]
    segs = sorted(d.get("transcripts") or [], key=lambda x: x.get("order") or 0)
    rows = [{"order": int(t.get("order") or 0), "uuid": t.get("uuid"), "speaker": f"S{t.get('label')}",
             "text": (t.get("transcript") or "").strip()}
            for t in segs if (t.get("transcript") or "").strip()]
    rows = rows[-40:] if after <= 0 else [r for r in rows if r["order"] > after]
    mx = max((r["order"] for r in rows), default=after)
    imgs = sorted(d.get("images") or [], key=lambda x: x.get("offset") or 0)
    images = [{"offset": im.get("offset"), "src": proxied(im["image_url"])} for im in imgs[-8:]]
    return {"live": True, "title": sp.get("title"), "segments": rows, "max_order": mx, "images": images}


def fetch_frame(url):
    if not (urlparse(url).hostname or "").endswith("aisense.com"):
        raise ValueError("only api.aisense.com frames are proxied")
    r = requests.get(url, cookies=otter().media, timeout=30)
    r.raise_for_status()
    return r.content, r.headers.get("content-type", "image/png")


def latest_slide():
    s = otter()
    sp = live_speech_cached(s)
    if not sp:
        return None
    d = s.get(OTTER + "speech", params={"userid": s.uid, "otid": sp["otid"]}, timeout=40).json()["speech"]
    imgs = sorted(d.get("images") or [], key=lambda x: x.get("offset") or 0)
    if not imgs:
        return None
    r = requests.get(imgs[-1]["image_url"], cookies=s.media, timeout=30)
    r.raise_for_status()
    return "data:image/png;base64," + base64.b64encode(r.content).decode()


def recap(text, use_slide=True):
    sys = ("You are catching someone up on a live meeting they glanced away from. From the recent transcript "
           "(may have fragments/mis-hears) and, if provided, the current shared screen, answer 'what were we "
           "just talking about?' Be tight and concrete: 2-4 short bullets on the current topic(s), plus any "
           "question or decision on the table right now. If a slide is shown, ground the recap in it. No preamble.")
    slide = latest_slide() if use_slide else None
    user = (f"Recent transcript:\n{text}\n\nWhat were we just talking about?")
    if slide:
        content = [{"type": "text", "text": user}, {"type": "image_url", "image_url": {"url": slide}}]
        model = VL_MODEL
    else:
        content = user
        model = TEXT_MODEL
    r = requests.post(NEAR_URL, headers={"Authorization": f"Bearer {NEAR_KEY}", "content-type": "application/json"},
                      json={"model": model, "max_tokens": 450, "temperature": 0.3,
                            "messages": [{"role": "system", "content": sys}, {"role": "user", "content": content}]},
                      timeout=90)
    r.raise_for_status()
    return {"summary": r.json()["choices"][0]["message"]["content"].strip(), "used_slide": bool(slide)}


def recap_to_matrix(use_slide=True):
    """On-demand 'catch you up' for a joiner: recap the live transcript and post it to Matrix.
    Stretch trigger (out of scope): fire this from Otter's presence socket on an actual new joiner."""
    st = live_state(0)
    if not st.get("live"):
        raise RuntimeError("no live meeting to recap")
    text = "\n".join(f"[{r['speaker']}] {r['text']}" for r in st["segments"])
    out = recap(text, use_slide=use_slide)
    title = st.get("title") or "live meeting"
    head = f"📍 catching you up — {title}"
    matrix.post(f"{head}\n{out['summary']}",
                html=f"<b>{head}</b><br>" + out["summary"].replace("\n", "<br>"))
    return out


# --- conversation decoder: typed-node graph over the live transcript ---
STATE = {}  # otid -> {topics: {label: id}, tcount, nodes: [...], done: set(uuid)}
DECODE_BATCH = 4
DECODE_MAX = 10   # cap segments per decode call so the model's JSON fits max_tokens (live backlog can be large)
DECODE_SYS = (
    "You decode a meeting transcript into a typed conversation graph. You get the topics already open and a "
    "batch of new numbered segments ([Sx] is a speaker cluster id). For each segment that carries meaning, emit "
    "one node; skip pure filler/backchannel ('yeah', 'right'). Kinds: topic (frames a subject), question, point "
    "(a substantive claim/idea), decision (something agreed/chosen), divergence (a tangent/disagreement), "
    "action_item (a to-do), aside. Give each node a short topic label, REUSING an open topic label verbatim when "
    "it fits, else a new short label. rel links it to the prior segment: new-topic|continues|reply-to|digression|"
    "resolves. Add \"good\":true on a node ONLY when it is a genuinely strong/insightful point — a crisp idea "
    "everyone reacts to or that visibly moves the discussion; be sparing. Return JSON only: "
    "{\"nodes\":[{\"i\":<segment index>,\"kind\":...,\"topic\":\"...\","
    "\"text\":\"<=12 word canonical phrasing\",\"rel\":...,\"good\":<true|omit>}]}")


def decode(open_topics, segs):
    listing = "\n".join(f"{i}. [{s['speaker']}] {s['text']}" for i, s in enumerate(segs))
    user = (f"Open topics: {', '.join(open_topics) or '(none yet)'}\n\n"
            f"New segments (in order):\n{listing}\n\nReturn JSON only.")
    r = requests.post(NEAR_URL, headers={"Authorization": f"Bearer {NEAR_KEY}", "content-type": "application/json"},
                      json={"model": TEXT_MODEL, "max_tokens": 800, "temperature": 0.2,
                            "response_format": {"type": "json_object"},
                            "messages": [{"role": "system", "content": DECODE_SYS},
                                         {"role": "user", "content": user}]},
                      timeout=90)
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"]).get("nodes", [])


def load_state(otid):
    """Load persisted STATE[otid] from disk (sets serialized as lists), else a fresh dict."""
    if otid in STATE:
        return STATE[otid]
    p = STATE_DIR / f"{otid}.json"
    if p.exists():
        d = json.loads(p.read_text())
        for k in ("done", "announced", "logged"):
            d[k] = set(d.get(k, []))
        STATE[otid] = d
    else:
        STATE[otid] = {"topics": {}, "tcount": 0, "nodes": [], "done": set(), "announced": set(),
                       "logged": set(), "started": False, "meta": {}}
    return STATE[otid]


def save_state(otid, st):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    d = dict(st, done=sorted(st["done"]), announced=sorted(st["announced"]), logged=sorted(st["logged"]))
    tmp = STATE_DIR / f"{otid}.json.tmp"
    tmp.write_text(json.dumps(d))
    tmp.rename(STATE_DIR / f"{otid}.json")


def append_transcript(otid, rows, logged):
    """Append uuids not yet in `logged` to /data/otter/live/<otid>.jsonl, idempotent by uuid."""
    new = [r for r in rows if r["uuid"] not in logged]
    if not new:
        return
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    with (LIVE_DIR / f"{otid}.jsonl").open("a") as f:
        for i, r in enumerate(new):
            f.write(json.dumps({"order": len(logged) + i, "uuid": r["uuid"],
                                "speaker": r["speaker"], "text": r["text"]}) + "\n")
    logged.update(r["uuid"] for r in new)


def graph_state():
    s = otter()
    sp = live_speech_cached(s)
    if not sp:
        return {"live": False}
    otid = sp["otid"]
    d = s.get(OTTER + "speech", params={"userid": s.uid, "otid": otid}, timeout=40).json()["speech"]
    rows = [{"uuid": t.get("uuid"), "speaker": f"S{t.get('label')}", "text": (t.get("transcript") or "").strip()}
            for t in sorted(d.get("transcripts") or [], key=lambda x: x.get("order") or 0)
            if (t.get("transcript") or "").strip()]
    st = load_state(otid)
    st.setdefault("meta", {})
    st["meta"].setdefault("title", sp.get("title") or "untitled")
    st["meta"].setdefault("started_at", sp.get("created_at") or sp.get("start_time"))
    append_transcript(otid, rows, st["logged"])
    if not st["started"]:
        st["started"] = True
        matrix.post(f"📡 meeting started — “{sp.get('title') or 'untitled'}”. Watching live; I'll surface decisions, good points, and a recap on request. Watch it live: {BASE_URL}/")
    new = [r for r in rows if r["uuid"] not in st["done"]][:DECODE_MAX]
    if len(new) >= DECODE_BATCH:
        for nd in decode(list(st["topics"]), new):
            i = nd.get("i")
            if not isinstance(i, int) or i >= len(new):
                continue
            label = nd.get("topic") or "misc"
            if label not in st["topics"]:
                st["tcount"] += 1
                st["topics"][label] = f"t{st['tcount']}"
            node = {"id": new[i]["uuid"], "speaker": new[i]["speaker"], "kind": nd.get("kind", "point"),
                    "text": nd.get("text") or new[i]["text"], "topic_id": st["topics"][label],
                    "topic": label, "rel": nd.get("rel", "continues"), "good": bool(nd.get("good"))}
            st["nodes"].append(node)
            if node["kind"] in ("decision", "action_item") and node["id"] not in st["announced"]:
                st["announced"].add(node["id"])
                matrix.post(f"🟢 {node['kind'].replace('_', ' ')}: {node['text']}  — {node['speaker']} · topic “{node['topic']}”")
            if node["good"] and node["id"] not in st["announced"]:
                st["announced"].add(node["id"])
                matrix.post(f"✨ good point — {node['text']} — {node['speaker']}")
        for r in new:
            st["done"].add(r["uuid"])
    save_state(otid, st)
    topics = [{"id": tid, "label": lbl, "node_ids": [n["id"] for n in st["nodes"] if n["topic_id"] == tid]}
              for lbl, tid in st["topics"].items()]
    decisions = [n["id"] for n in st["nodes"] if n["kind"] in ("decision", "action_item")]
    good = [n["id"] for n in st["nodes"] if n.get("good")]
    return {"live": True, "title": sp.get("title"), "topics": topics, "nodes": st["nodes"],
            "decisions": decisions, "good": good}


def live_otid():
    """otid of the currently-live meeting, or None (errors propagate)."""
    sp = live_speech(otter())
    return sp["otid"] if sp else None


# --- audience proposer: recommend a sharing tier; the owner accepts it (human-in-the-loop) ---
AUDIENCE_SYS = (
    "You are an audience proposer for a meeting copilot. Given a conversation's decoded insights and a "
    "transcript sample, judge who it's fit to share with. Tiers: \"public\" (anyone), \"cohort\" "
    "(semi-trusted peers), \"private\" (owner only). Be conservative: flag PII, named competitor call-outs, "
    "confidential, or half-baked/unresolved content as reasons NOT to go public. Return JSON only: "
    "{\"suggested\":\"private\"|\"cohort\"|\"public\",\"confidence\":<0-1>,\"rationale\":\"1-2 sentences\","
    "\"redactions\":[\"short note on anything sensitive to strip before sharing\"]}")


def propose_audience(otid):
    st = read_state(otid)
    if st is None:
        raise FileNotFoundError(f"no stored conversation {otid}")
    nodes = st.get("nodes", [])
    insights = [{"kind": n["kind"], "topic": n.get("topic"), "good": bool(n.get("good")), "text": n["text"]}
                for n in nodes if n.get("good") or n["kind"] in ("decision", "action_item", "topic")][:40]
    segs = read_segments(otid)
    sample = "\n".join(f"[{s['speaker']}] {s['text']}" for s in segs[:60])
    user = (f"Title: {(st.get('meta') or {}).get('title') or otid}\n\n"
            f"Decoded insights (decisions / action items / good points / topics):\n{json.dumps(insights)}\n\n"
            f"Transcript sample (start of meeting):\n{sample}\n\nReturn JSON only.")
    r = requests.post(NEAR_URL, headers={"Authorization": f"Bearer {NEAR_KEY}", "content-type": "application/json"},
                      json={"model": TEXT_MODEL, "max_tokens": 400, "temperature": 0.2,
                            "response_format": {"type": "json_object"},
                            "messages": [{"role": "system", "content": AUDIENCE_SYS},
                                         {"role": "user", "content": user}]},
                      timeout=90)
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])


def set_visibility(otid, visibility):
    if visibility not in ("private", "cohort", "public"):
        raise ValueError(f"bad visibility {visibility!r}")
    st = load_state(otid)
    st["visibility"] = visibility
    save_state(otid, st)
    return visibility


def visibility_of(otid):
    return (read_state(otid) or {}).get("visibility", "private")


def read_state(otid):
    p = STATE_DIR / f"{otid}.json"
    return json.loads(p.read_text()) if p.exists() else None


def read_segments(otid):
    p = LIVE_DIR / f"{otid}.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def conversations(live_sp):
    """List every stored conversation from DATA/state + DATA/live, newest first.
    Always includes the currently-live meeting, even before it has been decoded."""
    live = live_sp["otid"] if live_sp else None
    otids = {p.stem for p in STATE_DIR.glob("*.json")} | {p.stem for p in LIVE_DIR.glob("*.jsonl")}
    if live:
        otids.add(live)
    items = []
    for otid in otids:
        st = read_state(otid) or {}
        nodes = st.get("nodes", [])
        n_seg = sum(1 for _ in (LIVE_DIR / f"{otid}.jsonl").open()) if (LIVE_DIR / f"{otid}.jsonl").exists() else 0
        meta = st.get("meta") or {}
        items.append({
            "otid": otid, "title": meta.get("title") or (live_sp.get("title") if otid == live and live_sp else None) or otid,
            "started_at": meta.get("started_at"), "date": meta.get("date"),
            "visibility": st.get("visibility", "private"),
            "live": otid == live, "n_segments": n_seg, "n_nodes": len(nodes),
            "n_decisions": sum(1 for n in nodes if n.get("kind") in ("decision", "action_item")),
            "n_good": sum(1 for n in nodes if n.get("good"))})
    items.sort(key=lambda x: (x["live"], x.get("started_at") or x.get("date") or "", x["otid"]), reverse=True)
    return items


def transcript(otid):
    st = read_state(otid) or {}
    nodes = st.get("nodes", [])
    topics = [{"id": tid, "label": lbl, "node_ids": [n["id"] for n in nodes if n["topic_id"] == tid]}
              for lbl, tid in (st.get("topics") or {}).items()]
    meta = st.get("meta") or {}
    return {"otid": otid, "title": meta.get("title") or otid, "segments": read_segments(otid),
            "visibility": st.get("visibility", "private"),
            "topics": topics, "nodes": nodes,
            "decisions": [n["id"] for n in nodes if n["kind"] in ("decision", "action_item")],
            "good": [n["id"] for n in nodes if n.get("good")]}


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code); self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def log_message(self, *a):
        pass

    def _q(self, key):
        return parse_qs(urlparse(self.path).query).get(key, [""])[0]

    def _token(self):
        return self.headers.get("X-Auth-Token") or self._q("token")

    def is_owner(self):
        if not OWNER_TOKEN:
            return True
        t = self._token()
        return bool(t) and hmac.compare_digest(t, OWNER_TOKEN)

    def share_ok(self, otid):
        if not OWNER_TOKEN:
            return True
        sig = self.headers.get("X-Share-Sig") or self._q("sig")
        return bool(sig) and hmac.compare_digest(sig, share_sig(otid))

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            return self._send(200, (HERE / "index.html").read_bytes(), "text/html")
        if self.path.startswith("/sharelink"):
            if not self.is_owner():
                return self._send(401, json.dumps({"error": "owner only"}))
            otid = self._q("otid")
            return self._send(200, json.dumps({"otid": otid, "sig": share_sig(otid), "url": share_url(otid)}))
        if self.path.startswith("/transcript"):
            otid = self._q("otid")
            if not (self.is_owner() or self.share_ok(otid) or visibility_of(otid) == "public"):
                return self._send(401, json.dumps({"error": "unauthorized"}))
            try:
                return self._send(200, json.dumps(transcript(otid)))
            except Exception as e:
                return self._send(200, json.dumps({"error": f"{type(e).__name__}: {e}"}))
        if self.path.startswith("/conversations"):
            owner = self.is_owner()
            try:
                items = conversations(live_speech_cached(otter()))
            except Exception as e:
                return self._send(200, json.dumps({"error": f"{type(e).__name__}: {e}"}))
            if not owner:
                items = [c for c in items if c.get("visibility") == "public"]
            return self._send(200, json.dumps(items))
        if not self.is_owner():
            return self._send(401, json.dumps({"error": "owner only"}))
        if self.path.startswith("/audience"):
            try:
                return self._send(200, json.dumps(propose_audience(self._q("otid"))))
            except Exception as e:
                return self._send(200, json.dumps({"error": f"{type(e).__name__}: {e}"}))
        if self.path.startswith("/live"):
            after = int(re.search(r"after=(\d+)", self.path).group(1)) if "after=" in self.path else 0
            try:
                return self._send(200, json.dumps(live_state(after)))
            except Exception as e:
                return self._send(200, json.dumps({"error": f"{type(e).__name__}: {e}"}))
        if self.path.startswith("/graph"):
            try:
                return self._send(200, json.dumps(graph_state()))
            except Exception as e:
                return self._send(200, json.dumps({"error": f"{type(e).__name__}: {e}"}))
        if self.path.startswith("/frame"):
            u = parse_qs(urlparse(self.path).query).get("u", [""])[0]
            try:
                data, ctype = fetch_frame(base64.urlsafe_b64decode(u).decode())
                return self._send(200, data, ctype)
            except Exception as e:
                return self._send(502, f"{e}", "text/plain")
        return self._send(404, "{}")

    def do_POST(self):
        if not self.is_owner():
            return self._send(401, json.dumps({"error": "owner only"}))
        n = int(self.headers.get("content-length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/recap":
            try:
                return self._send(200, json.dumps(recap(body.get("text", ""), body.get("use_slide", True))))
            except Exception as e:
                return self._send(200, json.dumps({"error": f"{type(e).__name__}: {e}"}))
        if self.path.startswith("/visibility"):
            try:
                v = set_visibility(self._q("otid"), body["visibility"])
                return self._send(200, json.dumps({"otid": self._q("otid"), "visibility": v}))
            except Exception as e:
                return self._send(200, json.dumps({"error": f"{type(e).__name__}: {e}"}))
        if self.path == "/recap-matrix":
            try:
                return self._send(200, json.dumps(recap_to_matrix(body.get("use_slide", True))))
            except Exception as e:
                return self._send(200, json.dumps({"error": f"{type(e).__name__}: {e}"}))
        return self._send(404, "{}")


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"otter live recap: http://{host}:{PORT}   (text={TEXT_MODEL}, vision={VL_MODEL})")
    ThreadingHTTPServer((host, PORT), H).serve_forever()
