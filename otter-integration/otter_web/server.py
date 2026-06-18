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
import base64, json, os, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import browser_cookie3 as bc
import requests

HERE = Path(__file__).parent
PORT = int(os.environ.get("PORT", 8137))
OTTER = "https://otter.ai/forward/api/v1/"
NEAR_URL = "https://cloud-api.near.ai/v1/chat/completions"
TEXT_MODEL = os.environ.get("NEAR_MODEL", "deepseek-ai/DeepSeek-V4-Flash")
VL_MODEL = os.environ.get("NEAR_VL_MODEL", "google/gemini-2.5-flash")


def near_key():
    if os.environ.get("NEAR_KEY"):
        return os.environ["NEAR_KEY"]
    envf = Path.home() / "projects" / "aishley" / ".env.local"
    return re.search(r"^NEAR_KEY=(.+)$", envf.read_text(), re.M).group(1).strip()


NEAR_KEY = near_key()


def otter():
    jar = bc.chrome(domain_name="otter.ai")
    s = requests.Session()
    s.cookies = jar
    s.headers.update({"referer": "https://otter.ai/", "user-agent": "Mozilla/5.0"})
    s.uid = s.get(OTTER + "user", timeout=30).json()["userid"]
    s.media = {c.name: c.value for c in jar if c.name in ("sessionid", "csrftoken")}
    return s


def live_speech(s):
    speeches = s.get(OTTER + "speeches", params={"userid": s.uid, "page_size": 20, "source": "owned"},
                     timeout=40).json()["speeches"]
    live = [x for x in speeches if x.get("live_status") == "live"]
    return live[0] if live else None


def proxied(url):
    return "/frame?u=" + base64.urlsafe_b64encode(url.encode()).decode()


def live_state(after):
    s = otter()
    sp = live_speech(s)
    if not sp:
        return {"live": False}
    d = s.get(OTTER + "speech", params={"userid": s.uid, "otid": sp["otid"]}, timeout=40).json()["speech"]
    segs = sorted(d.get("transcripts") or [], key=lambda x: x.get("order") or 0)
    rows = [{"order": int(t.get("order") or 0), "text": (t.get("transcript") or "").strip()}
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
    sp = live_speech(s)
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


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code); self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            return self._send(200, (HERE / "index.html").read_bytes(), "text/html")
        if self.path.startswith("/live"):
            after = int(re.search(r"after=(\d+)", self.path).group(1)) if "after=" in self.path else 0
            try:
                return self._send(200, json.dumps(live_state(after)))
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
        n = int(self.headers.get("content-length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/recap":
            try:
                return self._send(200, json.dumps(recap(body.get("text", ""), body.get("use_slide", True))))
            except Exception as e:
                return self._send(200, json.dumps({"error": f"{type(e).__name__}: {e}"}))
        return self._send(404, "{}")


if __name__ == "__main__":
    print(f"otter live recap: http://localhost:{PORT}   (text={TEXT_MODEL}, vision={VL_MODEL})")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
