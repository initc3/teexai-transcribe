import os
import io
import json
import wave
import asyncio
from datetime import datetime, timezone

import httpx
import numpy as np
import sherpa_onnx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

API_KEY = os.environ["NEAR_API_KEY"]
BASE = "https://cloud-api.near.ai/v1"
NOTES_FILE = "notes.json"

# ---------- speaker-id config ----------
MODELS_DIR = os.environ.get("MODELS_DIR", "models")
SEG_MODEL = os.environ.get("SEG_MODEL", os.path.join(MODELS_DIR, "segmentation.onnx"))
EMB_MODEL = os.environ.get("EMB_MODEL", os.path.join(MODELS_DIR, "embedding.onnx"))
# Voiceprints are biometric identifiers — keep them inside the CVM. VOICEPRINT_DIR
# points at a persistent (on Phala: encrypted) volume so they survive redeploy.
VOICEPRINT_DIR = os.environ.get("VOICEPRINT_DIR", ".")
VOICEPRINTS_FILE = os.path.join(VOICEPRINT_DIR, "voiceprints.json")
# Open-set match bar for naming a speaker; below it → unknown (speaker_NN).
THR = float(os.environ.get("SPEAKER_THRESHOLD", "0.5"))
# Agglomerative clustering bar used only to split a recording into turns.
CLUSTER_THR = float(os.environ.get("CLUSTER_THRESHOLD", "0.5"))
SR = 16000
CHUNK_SEC = 45  # near.ai transcription 502s past ~60s/2MB; chunk under that

app = FastAPI()


def headers():
    return {"Authorization": f"Bearer {API_KEY}"}


# ---------- audio decode ----------

async def to_pcm(data: bytes) -> np.ndarray:
    """Decode arbitrary audio to 16 kHz mono float32 PCM for local diarization + ASR windows."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-i", "pipe:0", "-ar", str(SR), "-ac", "1",
        "-f", "f32le", "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate(data)
    if proc.returncode != 0:
        raise RuntimeError(err.decode()[-500:])
    return np.frombuffer(out, dtype=np.float32)


# ---------- chunked ASR (near.ai 502s past ~60s/2MB, so window the audio) ----------

def _pcm_to_wav_bytes(samples: np.ndarray) -> bytes:
    pcm16 = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm16)
    return buf.getvalue()


def _windows(turn_ends, total):
    # cut at speaker-turn ends (silence) when possible, hard-cap at CHUNK_SEC
    cuts, t = [0.0], 0.0
    while t < total:
        t = max([e for e in turn_ends if t < e <= t + CHUNK_SEC], default=t + CHUNK_SEC)
        cuts.append(min(t, total))
    if len(cuts) > 2 and cuts[-1] - cuts[-2] < 1.0:  # absorb trailing sliver
        cuts.pop(-2)
    return list(zip(cuts, cuts[1:]))


async def _asr_window(client, chunk: np.ndarray, offset: float):
    r = await client.post(
        f"{BASE}/audio/transcriptions",
        headers=headers(),
        files={"file": ("a.wav", _pcm_to_wav_bytes(chunk), "audio/wav")},
        data={"model": "openai/whisper-large-v3", "response_format": "verbose_json"},
    )
    r.raise_for_status()
    j = r.json()
    segs = [{"start": s.get("start", 0.0) + offset, "end": s.get("end", 0.0) + offset,
             "text": s.get("text", "")} for s in j.get("segments", [])]
    if not segs and j.get("text"):  # no per-segment timing → one span for the window
        segs = [{"start": offset, "end": offset + len(chunk) / SR, "text": j["text"]}]
    return segs


async def transcribe_chunks(samples: np.ndarray, turn_ends):
    total = len(samples) / SR
    segs = []
    async with httpx.AsyncClient(timeout=120) as client:
        for ws, we in _windows(turn_ends, total):
            chunk = samples[int(ws * SR):int(we * SR)]
            if chunk.size:
                segs += await _asr_window(client, chunk, ws)
    return segs


# ---------- prosody (per-segment, numpy-only redaction prior) ----------

def f0(x: np.ndarray) -> float:
    n = len(x)
    if n < SR // 75 or np.sqrt(np.mean(x ** 2)) < 1e-4:
        return 0.0
    x = x - x.mean()
    f = np.fft.rfft(x, 2 * n)
    corr = np.fft.irfft(f * np.conj(f))[:n]
    lo, hi = SR // 400, min(SR // 75, n)
    return round(SR / (lo + int(np.argmax(corr[lo:hi]))), 1)


def prosody(x: np.ndarray):
    return {"f0": f0(x), "rms": round(float(np.sqrt(np.mean(x ** 2))), 4)}


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    samples = await to_pcm(await file.read())
    segs = await transcribe_chunks(samples, [])
    return {"text": "".join(s["text"] for s in segs).strip(),
            "duration": len(samples) / SR, "segments": len(segs)}


# ---------- speaker identification (in-CVM) ----------
# Diarization, embedding, and voiceprint matching all run locally; only ASR text
# is fetched from near.ai. Heavy models are built lazily so import/startup is cheap.

_extractor = None
_diarizer = None
_manager = None
_voiceprints: dict = {}  # {name: {"emb": [float], "clips": int}}; loaded by get_manager()


def get_extractor():
    global _extractor
    if _extractor is None:
        _extractor = sherpa_onnx.SpeakerEmbeddingExtractor(
            sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=EMB_MODEL))
    return _extractor


def get_diarizer():
    global _diarizer
    if _diarizer is None:
        cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=SEG_MODEL)),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=EMB_MODEL),
            clustering=sherpa_onnx.FastClusteringConfig(num_clusters=-1, threshold=CLUSTER_THR),
            min_duration_on=0.3, min_duration_off=0.5)
        _diarizer = sherpa_onnx.OfflineSpeakerDiarization(cfg)
    return _diarizer


def get_manager():
    """Embedding manager seeded from the persisted voiceprint store."""
    global _manager, _voiceprints
    if _manager is None:
        ext = get_extractor()
        _manager = sherpa_onnx.SpeakerEmbeddingManager(ext.dim)
        _voiceprints = {}
        if os.path.exists(VOICEPRINTS_FILE):
            with open(VOICEPRINTS_FILE) as f:
                _voiceprints = json.load(f)
        for name, vp in _voiceprints.items():
            _manager.add(name, np.array(vp["emb"], dtype=np.float32))
    return _manager


def save_voiceprints():
    os.makedirs(VOICEPRINT_DIR, exist_ok=True)
    with open(VOICEPRINTS_FILE, "w") as f:
        json.dump(_voiceprints, f)


def embed(samples: np.ndarray) -> np.ndarray:
    ext = get_extractor()
    s = ext.create_stream()
    s.accept_waveform(sample_rate=SR, waveform=np.ascontiguousarray(samples))
    s.input_finished()
    return np.array(ext.compute(s), dtype=np.float32)


def recognize(samples: np.ndarray):
    """Return an enrolled name for this audio, or None if below threshold."""
    mgr = get_manager()
    if not _voiceprints:
        return None
    name = mgr.search(embed(samples), threshold=THR)
    return name or None


@app.post("/api/enroll")
async def enroll(name: str = Form(...), file: UploadFile = File(...)):
    samples = await to_pcm(await file.read())
    if samples.size < SR // 2:
        raise HTTPException(400, "reference clip too short (need ≥0.5s)")
    emb = embed(samples)
    mgr = get_manager()
    vp = _voiceprints.get(name)
    if vp:  # average new clip into the existing centroid ("build up the vector")
        n = vp["clips"]
        emb = (np.array(vp["emb"], dtype=np.float32) * n + emb) / (n + 1)
        _voiceprints[name] = {"emb": emb.tolist(), "clips": n + 1}
        mgr.remove(name)
    else:
        _voiceprints[name] = {"emb": emb.tolist(), "clips": 1}
    mgr.add(name, emb)
    save_voiceprints()
    return {"name": name, "dim": int(emb.size), "clips": _voiceprints[name]["clips"]}


@app.get("/api/voiceprints")
async def voiceprints():
    get_manager()
    return {"names": [{"name": n, "clips": vp["clips"]} for n, vp in _voiceprints.items()]}


@app.delete("/api/voiceprints/{name}")
async def delete_voiceprint(name: str):
    mgr = get_manager()
    if name not in _voiceprints:
        raise HTTPException(404, "no such voiceprint")
    mgr.remove(name)
    del _voiceprints[name]
    save_voiceprints()
    return {"deleted": name}


def _diarize(samples: np.ndarray):
    """Blocking: return turns [{start, end, speaker}] sorted by start time."""
    result = get_diarizer().process(samples).sort_by_start_time()
    return [{"start": r.start, "end": r.end, "speaker": r.speaker} for r in result]


@app.post("/api/transcribe_diarized")
async def transcribe_diarized(file: UploadFile = File(...)):
    samples = await to_pcm(await file.read())
    # Diarize locally (CPU-bound → thread); turn ends double as ASR window cut points.
    turns = await asyncio.to_thread(_diarize, samples)

    # Resolve a label per cluster from its longest turn: enrolled name or speaker_NN.
    labels = {}
    for spk in {t["speaker"] for t in turns}:
        longest = max((t for t in turns if t["speaker"] == spk),
                      key=lambda t: t["end"] - t["start"])
        clip = samples[int(longest["start"] * SR):int(longest["end"] * SR)]
        name = recognize(clip) if clip.size >= SR // 2 else None
        labels[spk] = name or f"speaker_{spk:02d}"

    # Chunked ASR (cut at turn ends) so long meetings don't 502 on near.ai.
    asr_segs = await transcribe_chunks(samples, [t["end"] for t in turns])

    # Attach each ASR text segment to the diarization turn it overlaps most.
    def overlap(a0, a1, b0, b1):
        return max(0.0, min(a1, b1) - max(a0, b0))

    segments = []
    for s in asr_segs:
        best = max(turns, key=lambda t: overlap(s["start"], s["end"], t["start"], t["end"]), default=None)
        spk = best["speaker"] if best and overlap(s["start"], s["end"], best["start"], best["end"]) > 0 else -1
        clip = samples[int(s["start"] * SR):int(s["end"] * SR)]
        segments.append({"start": s["start"], "end": s["end"], "speaker": spk,
                         "label": labels.get(spk, "speaker_??"), "text": s["text"].strip(),
                         "prosody": prosody(clip) if clip.size else None})

    text = "".join(s["text"] for s in asr_segs).strip()
    return {"text": text, "duration": len(samples) / SR, "speakers": labels, "segments": segments}


# ---------- chat (summarize / extract) ----------

class ChatReq(BaseModel):
    messages: list
    model: str = "anthropic/claude-haiku-4-5"


@app.post("/api/chat")
async def chat(req: ChatReq):
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{BASE}/chat/completions",
            headers=headers(),
            json={"model": req.model, "max_tokens": 1024, "messages": req.messages},
        )
    return JSONResponse(r.json(), status_code=r.status_code)


@app.post("/api/chat/stream")
async def chat_stream(req: ChatReq):
    async def gen():
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST", f"{BASE}/chat/completions", headers=headers(),
                json={"model": req.model, "max_tokens": 1024, "stream": True,
                      "stream_options": {"include_usage": True}, "messages": req.messages},
            ) as r:
                async for line in r.aiter_lines():
                    if line:
                        yield line + "\n"
    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------- tool-using agent ----------

TOOLS = [
    {"type": "function", "function": {
        "name": "get_current_time", "description": "Get the current UTC time.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "save_note", "description": "Save a note for the user.",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string", "description": "Note content"}}, "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "list_notes", "description": "List all saved notes.",
        "parameters": {"type": "object", "properties": {}}}},
]


def load_notes():
    if not os.path.exists(NOTES_FILE):
        return []
    with open(NOTES_FILE) as f:
        return json.load(f)


def run_tool(name, args):
    if name == "get_current_time":
        return datetime.now(timezone.utc).isoformat()
    if name == "save_note":
        notes = load_notes()
        notes.append({"text": args["text"], "at": datetime.now(timezone.utc).isoformat()})
        with open(NOTES_FILE, "w") as f:
            json.dump(notes, f, indent=2)
        return f"Saved. {len(notes)} note(s) total."
    if name == "list_notes":
        return json.dumps(load_notes())
    raise ValueError(f"unknown tool {name}")


class AgentReq(BaseModel):
    messages: list
    model: str = "anthropic/claude-haiku-4-5"


@app.post("/api/agent")
async def agent(req: AgentReq):
    messages = list(req.messages)
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    async with httpx.AsyncClient(timeout=120) as client:
        for _ in range(6):
            r = await client.post(
                f"{BASE}/chat/completions",
                headers=headers(),
                json={"model": req.model, "max_tokens": 1024,
                      "messages": messages, "tools": TOOLS},
            )
            if r.status_code != 200:
                return JSONResponse(r.json(), status_code=r.status_code)
            body = r.json()
            for k in usage:
                usage[k] += body.get("usage", {}).get(k, 0)
            msg = body["choices"][0]["message"]
            messages.append(msg)
            calls = msg.get("tool_calls")
            if not calls:
                return {"reply": msg.get("content", ""), "messages": messages, "usage": usage}
            for c in calls:
                result = run_tool(c["function"]["name"],
                                  json.loads(c["function"]["arguments"] or "{}"))
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": str(result)})
    return {"reply": "(stopped: too many tool steps)", "messages": messages, "usage": usage}


@app.get("/")
def index():
    return FileResponse("static/index.html")
