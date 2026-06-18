"""OpenAI /v1/audio/transcriptions -> near.ai TEE whisper-large-v3.
Vexa's bot POSTs WAV here; inference runs in near's enclave, not local CPU."""
import os, time, collections, httpx
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse

NEAR = "https://cloud-api.near.ai/v1/audio/transcriptions"
KEY = os.environ["NEAR_API_KEY"]
app = FastAPI()

STATS = {"chunks": 0, "bytes": 0, "inflight": 0, "last_ms": 0, "last_ts": 0,
         "recent": collections.deque(maxlen=40)}

@app.get("/health")
def health():
    return {"status": "healthy", "backend": "near.ai whisper-large-v3"}

@app.get("/stats")
def stats():
    return {k: (list(v) if k == "recent" else v) for k, v in STATS.items()}

@app.post("/v1/audio/transcriptions")
async def transcribe(file: UploadFile = File(...),
                     language: str = Form(None),
                     response_format: str = Form("verbose_json")):
    data = await file.read()
    form = {"model": "openai/whisper-large-v3", "response_format": "verbose_json"}
    if language and language != "auto":
        form["language"] = language
    STATS["inflight"] += 1
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(NEAR, headers={"Authorization": f"Bearer {KEY}"},
                             files={"file": (file.filename or "a.wav", data, "audio/wav")},
                             data=form)
    finally:
        STATS["inflight"] -= 1
    ms = round((time.monotonic() - t0) * 1000)
    STATS["chunks"] += 1; STATS["bytes"] += len(data)
    STATS["last_ms"] = ms; STATS["last_ts"] = time.time()
    STATS["recent"].append({"ts": time.time(), "bytes": len(data), "ms": ms, "status": r.status_code})
    return JSONResponse(status_code=r.status_code, content=r.json())
