import numpy as np
from fastapi import FastAPI, WebSocket, Request
from faster_whisper import WhisperModel

app = FastAPI()
model = WhisperModel("base", download_root="/models", compute_type="int8")
bufs = {}  # role -> [np.float32 arrays]


@app.websocket("/pcm")
async def pcm(ws: WebSocket):
    await ws.accept()
    role = ws.query_params.get("role", "?")
    bufs.setdefault(role, [])
    try:
        while True:
            data = await ws.receive_bytes()
            bufs[role].append(np.frombuffer(data, dtype=np.float32))
    except Exception:
        pass


@app.post("/log")
async def log(req: Request):
    print("BOT", (await req.body()).decode("utf-8", "replace")[:400], flush=True)
    return {}


def transcribe(role):
    chunks = bufs.get(role, [])
    if not chunks:
        return {"text": "", "samples": 0}
    audio = np.concatenate(chunks).astype(np.float32)
    segs, _ = model.transcribe(audio, language="en", beam_size=1, vad_filter=False)
    return {"text": " ".join(s.text for s in segs).strip(), "samples": int(audio.size)}


@app.get("/results")
def results():
    return {role: transcribe(role) for role in ("listener", "eavesdropper")}
