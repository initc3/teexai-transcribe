"""Live transcript + "what were we just talking about?" recap.
Consumes Vexa gateway WS (audio->near whisper) into a rolling buffer,
and recaps recent talk via near chat (teexai /api/chat). No new infra."""
import asyncio, json, os, httpx, websockets
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

TOKEN = open('/tmp/vexa-token.txt').read().strip()
MEET = os.environ.get("MEET", "ecp-wcwr-bgn")
WS = "ws://localhost:8056/ws"
CHAT = "http://localhost:8000/api/chat"   # teexai -> near chat (confidential)

app = FastAPI()
segs = {}   # key -> {speaker,text,t}

def _ingest(msg):
    # bot publishes {type:'transcript', speaker, confirmed:[...], pending:[...]}
    sp = msg.get("speaker") or "?"
    for s in (msg.get("confirmed") or []):
        t = (s.get("text") or "").strip()
        if not t:
            continue
        key = s.get("segment_id") or s.get("absolute_start_time") or f"{s.get('start')}-{sp}"
        segs[key] = {"speaker": s.get("speaker") or sp, "text": t,
                     "t": s.get("absolute_start_time") or s.get("start") or ""}

async def consume():
    while True:
        try:
            async with websockets.connect(WS, additional_headers={"X-API-Key": TOKEN}) as ws:
                await ws.send(json.dumps({"action": "subscribe",
                    "meetings": [{"platform": "google_meet", "native_id": MEET}]}))
                async for raw in ws:
                    m = json.loads(raw)
                    if m.get("type") not in (None, "subscribed", "pong", "error"):
                        _ingest(m)
        except Exception as e:
            print("ws reconnect:", e); await asyncio.sleep(2)

@app.on_event("startup")
async def _start():
    asyncio.create_task(consume())

def transcript_text(limit=80):
    rows = sorted(segs.values(), key=lambda x: str(x["t"]))[-limit:]
    return "\n".join(f"{r['speaker']}: {r['text']}" for r in rows)

@app.get("/transcript.json")
def tjson():
    return JSONResponse(sorted(segs.values(), key=lambda x: str(x["t"])))

@app.get("/pipeline")
async def pipeline():
    async with httpx.AsyncClient(timeout=5) as c:
        r = await c.get("http://localhost:8001/stats")
    return JSONResponse(r.json())

@app.get("/recap")
async def recap():
    convo = transcript_text()
    if not convo:
        return {"recap": "(nothing transcribed yet — talk in the meeting)"}
    prompt = ("Here is the recent meeting transcript:\n\n" + convo +
              "\n\nIn 2-3 sentences, what were we just talking about? Be concrete.")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(CHAT, json={"messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    d = r.json()
    msg = d.get("choices", [{}])[0].get("message", {}).get("content") or d.get("content") or json.dumps(d)[:400]
    return {"recap": msg}

@app.get("/", response_class=HTMLResponse)
def index():
    return """<!doctype html><meta charset=utf-8><title>Meeting recap</title>
<style>body{font:15px system-ui;margin:0;display:flex;height:100vh}
#l{flex:1;overflow:auto;padding:16px;border-right:1px solid #ddd}
#r{width:340px;padding:16px;background:#fafafa}
.s{margin:.3em 0}.sp{font-weight:600;color:#444}
button{font:15px system-ui;padding:8px 14px;cursor:pointer}
#recap{margin-top:12px;white-space:pre-wrap;background:#fff;border:1px solid #ddd;padding:12px;border-radius:8px;min-height:60px}</style>
<div id=l><h3>Live transcript</h3><div id=t></div></div>
<div id=r>
<h3>Pipeline <span id=dot class=dot></span></h3>
<div id=pipe class=pipe>
 <div><b id=chunks>0</b> chunks → near TEE</div>
 <div><b id=kb>0</b> KB sent · <b id=infl>0</b> in‑flight</div>
 <div>last chunk <b id=ms>–</b> ms</div>
 <div id=spark class=spark></div>
</div>
<h3>Recap</h3><button onclick=recap()>What were we just talking about?</button>
<div id=recap>—</div></div>
<style>
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;background:#ccc;vertical-align:middle}
.dot.on{background:#19c37d;box-shadow:0 0 8px #19c37d}
.pipe{font-size:13px;line-height:1.7;background:#fff;border:1px solid #ddd;border-radius:8px;padding:10px;margin-bottom:14px}
.spark{display:flex;align-items:flex-end;gap:2px;height:34px;margin-top:8px}
.spark i{width:5px;background:#19c37d;border-radius:1px;opacity:.85}
</style>
<script>
async function tick(){let s=await (await fetch('/transcript.json')).json();
 document.getElementById('t').innerHTML=s.map(x=>`<div class=s><span class=sp>${x.speaker}:</span> ${x.text}</div>`).join('');
 let l=document.getElementById('l');l.scrollTop=l.scrollHeight;}
let lastChunks=0;
async function pipe(){let p=await (await fetch('/pipeline')).json();
 document.getElementById('chunks').textContent=p.chunks;
 document.getElementById('kb').textContent=(p.bytes/1024).toFixed(0);
 document.getElementById('infl').textContent=p.inflight;
 document.getElementById('ms').textContent=p.last_ms||'–';
 let active=p.inflight>0||p.chunks>lastChunks;lastChunks=p.chunks;
 document.getElementById('dot').className='dot'+(active?' on':'');
 let r=(p.recent||[]).slice(-24),mx=Math.max(1,...r.map(x=>x.ms));
 document.getElementById('spark').innerHTML=r.map(x=>{let h=6+28*x.ms/mx;
   let col=x.status!=200?'#e0564f':x.ms>2500?'#e6a23c':'#19c37d';
   return `<i style="height:${h}px;background:${col}" title="${x.ms}ms ${(x.bytes/1024).toFixed(0)}KB"></i>`}).join('');}
async function recap(){document.getElementById('recap').textContent='thinking…';
 let r=await (await fetch('/recap')).json();document.getElementById('recap').textContent=r.recap;}
setInterval(tick,2000);setInterval(pipe,1000);tick();pipe();
</script>"""
