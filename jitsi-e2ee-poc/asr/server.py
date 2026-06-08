import io, os
import numpy as np
import soundfile as sf
import httpx
from fastapi import FastAPI, WebSocket, Request

API_KEY = os.environ["NEAR_API_KEY"]
BASE = "https://cloud-api.near.ai/v1"
SR = 16000

app = FastAPI()
bufs = {}  # role -> [np.float32]


@app.websocket("/pcm")
async def pcm(ws: WebSocket):
    await ws.accept()
    role = ws.query_params.get("role", "?")
    bufs.setdefault(role, [])
    try:
        while True:
            bufs[role].append(np.frombuffer(await ws.receive_bytes(), dtype=np.float32))
    except Exception:
        pass


@app.post("/log")
async def log(req: Request):
    print("BOT", (await req.body()).decode("utf-8", "replace")[:400], flush=True)
    return {}


async def transcribe(role):
    chunks = bufs.get(role, [])
    if not chunks:
        return {"text": "", "samples": 0}
    audio = np.concatenate(chunks).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, SR, format="WAV", subtype="PCM_16")
    buf.seek(0)
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(
            f"{BASE}/audio/transcriptions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            files={"file": ("a.wav", buf, "audio/wav")},
            data={"model": "openai/whisper-large-v3", "response_format": "json"},
        )
    r.raise_for_status()
    return {"text": r.json().get("text", "").strip(), "samples": int(audio.size)}


@app.get("/results")
async def results():
    return {role: await transcribe(role) for role in ("listener", "eavesdropper")}
