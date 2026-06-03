import os
import json
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

app = FastAPI()


def headers():
    return {"Authorization": f"Bearer {API_KEY}"}


# ---------- transcription ----------

async def to_ogg(data: bytes) -> bytes:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-i", "pipe:0", "-ar", "16000", "-ac", "1",
        "-c:a", "libopus", "-f", "ogg", "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate(data)
    if proc.returncode != 0:
        raise RuntimeError(err.decode()[-500:])
    return out


async def to_pcm(data: bytes) -> np.ndarray:
    """Decode arbitrary audio to 16 kHz mono float32 PCM for local diarization."""
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


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    audio = await to_ogg(await file.read())
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{BASE}/audio/transcriptions",
            headers=headers(),
            files={"file": ("audio.ogg", audio, "audio/ogg")},
            data={"model": "openai/whisper-large-v3", "response_format": "verbose_json"},
        )
    if r.status_code != 200:
        return JSONResponse(r.json(), status_code=r.status_code)
    j = r.json()
    return {"text": j.get("text", ""), "duration": j.get("duration"),
            "segments": len(j.get("segments", []))}


# ---------- speaker identification (in-CVM) ----------
# Diarization, embedding, and voiceprint matching all run locally; only ASR text
# is fetched from near.ai. Heavy models are built lazily so the endpoints above
# (and import/startup) don't pay the cost.

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
    s.accept_waveform(sample_rate=SR, waveform=samples)
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
    data = await file.read()
    samples = await to_pcm(data)

    # Diarize locally (CPU-bound → thread) while ASR text is fetched from near.ai.
    async def asr():
        ogg = await to_ogg(data)
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{BASE}/audio/transcriptions", headers=headers(),
                files={"file": ("audio.ogg", ogg, "audio/ogg")},
                data={"model": "openai/whisper-large-v3", "response_format": "verbose_json"})
        if r.status_code != 200:
            raise HTTPException(r.status_code, r.text)
        return r.json()

    turns, asr_json = await asyncio.gather(asyncio.to_thread(_diarize, samples), asr())

    # Resolve a label per cluster from its longest turn: enrolled name or speaker_NN.
    labels = {}
    for spk in {t["speaker"] for t in turns}:
        longest = max((t for t in turns if t["speaker"] == spk),
                      key=lambda t: t["end"] - t["start"])
        clip = samples[int(longest["start"] * SR):int(longest["end"] * SR)]
        name = recognize(clip) if clip.size >= SR // 2 else None
        labels[spk] = name or f"speaker_{spk:02d}"

    # Attach each ASR text segment to the diarization turn it overlaps most.
    def overlap(a0, a1, b0, b1):
        return max(0.0, min(a1, b1) - max(a0, b0))

    segments = []
    for s in asr_json.get("segments", []):
        s0, s1 = s.get("start", 0.0), s.get("end", 0.0)
        best = max(turns, key=lambda t: overlap(s0, s1, t["start"], t["end"]), default=None)
        spk = best["speaker"] if best and overlap(s0, s1, best["start"], best["end"]) > 0 else -1
        segments.append({"start": s0, "end": s1, "speaker": spk,
                         "label": labels.get(spk, "speaker_??"), "text": s.get("text", "").strip()})

    # Fallback when ASR returns no per-segment timing but does return text.
    if not segments and asr_json.get("text"):
        spk = turns[0]["speaker"] if turns else 0
        segments = [{"start": 0.0, "end": asr_json.get("duration", 0.0), "speaker": spk,
                     "label": labels.get(spk, "speaker_00"), "text": asr_json["text"].strip()}]

    return {"text": asr_json.get("text", ""), "duration": asr_json.get("duration"),
            "speakers": labels, "segments": segments}


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
