import os
import io
import json
import asyncio
from datetime import datetime, timezone

import httpx
import numpy as np
import soundfile as sf
import sherpa_onnx
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

API_KEY = os.environ["NEAR_API_KEY"]
BASE = "https://cloud-api.near.ai/v1"
NOTES_FILE = "notes.json"
SR = 16000
CHUNK_SEC = 45  # near.ai transcription 502s past ~60s/2MB; chunk under that

app = FastAPI()


def headers():
    return {"Authorization": f"Bearer {API_KEY}"}


# ---------- transcription + in-CVM diarization ----------

SD = sherpa_onnx.OfflineSpeakerDiarization(
    sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model="models/segmentation.onnx"), num_threads=2),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model="models/embedding.onnx", num_threads=2),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=-1, threshold=0.5),
        min_duration_on=0.3, min_duration_off=0.5))


# ---------- speaker recognition (enrolled voiceprints, same embedding.onnx) ----------

EX = sherpa_onnx.SpeakerEmbeddingExtractor(
    sherpa_onnx.SpeakerEmbeddingExtractorConfig(model="models/embedding.onnx", num_threads=2))
MGR = sherpa_onnx.SpeakerEmbeddingManager(EX.dim)
THR = 0.6  # open-set recognition bar (cosine); stricter than the 0.5 clustering distance
VOICEPRINTS_FILE = "voiceprints.json"  # sealed-storage candidate; lives in-CVM
VP = {}
if os.path.exists(VOICEPRINTS_FILE):
    VP = json.load(open(VOICEPRINTS_FILE))
    for n, e in VP.items():
        MGR.add(n, np.array(e, dtype=np.float32))


def embed(audio):
    st = EX.create_stream()
    st.accept_waveform(SR, np.ascontiguousarray(audio))
    st.input_finished()
    return np.array(EX.compute(st), dtype=np.float32)


def recognize(audio, turns):
    by_k = {}
    for s, e, k in turns:
        by_k.setdefault(k, []).append((e - s, s, e))
    out = {}
    for k, segs in by_k.items():  # match each cluster on its longest turn
        _, s, e = max(segs)
        out[k] = MGR.search(embed(audio[int(s * SR):int(e * SR)]), THR) or None
    return out


# ---------- prosody (per-segment, numpy-only redaction prior) ----------

def f0(x):
    n = len(x)
    if n < SR // 75 or np.sqrt(np.mean(x ** 2)) < 1e-4:
        return 0.0
    x = x - x.mean()
    f = np.fft.rfft(x, 2 * n)
    corr = np.fft.irfft(f * np.conj(f))[:n]
    lo, hi = SR // 400, min(SR // 75, n)
    return round(SR / (lo + int(np.argmax(corr[lo:hi]))), 1)


def prosody(x):
    return {"f0": f0(x), "rms": round(float(np.sqrt(np.mean(x ** 2))), 4)}


async def to_wav(data: bytes) -> np.ndarray:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-i", "pipe:0", "-ar", str(SR), "-ac", "1", "-f", "wav", "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate(data)
    if proc.returncode != 0:
        raise RuntimeError(err.decode()[-500:])
    audio, _ = sf.read(io.BytesIO(out), dtype="float32", always_2d=True)
    return audio[:, 0]


def diarize(audio):
    return [(r.start, r.end, r.speaker) for r in SD.process(audio).sort_by_start_time()]


def windows(turns, total):
    # cut at speaker-turn ends (silence) when possible, hard-cap at CHUNK_SEC
    ends = [e for _, e, _ in turns]
    cuts, t = [0.0], 0.0
    while t < total:
        t = max([e for e in ends if t < e <= t + CHUNK_SEC], default=t + CHUNK_SEC)
        cuts.append(min(t, total))
    if len(cuts) > 2 and cuts[-1] - cuts[-2] < 1.0:  # absorb trailing sliver
        cuts.pop(-2)
    return list(zip(cuts, cuts[1:]))


async def transcribe_window(client, chunk, offset):
    buf = io.BytesIO()
    sf.write(buf, chunk, SR, format="WAV", subtype="PCM_16")
    buf.seek(0)
    r = await client.post(
        f"{BASE}/audio/transcriptions",
        headers=headers(),
        files={"file": ("a.wav", buf, "audio/wav")},
        data={"model": "openai/whisper-large-v3", "response_format": "verbose_json",
              "timestamp_granularities[]": "segment"},
    )
    r.raise_for_status()
    return [{"start": s["start"] + offset, "end": s["end"] + offset, "text": s["text"]}
            for s in r.json()["segments"]]


async def transcribe_chunks(audio, turns):
    total = len(audio) / SR
    segs = []
    async with httpx.AsyncClient(timeout=120) as client:
        for ws, we in windows(turns, total):
            segs += await transcribe_window(client, audio[int(ws * SR):int(we * SR)], ws)
    return segs


def assign_speaker(seg, turns):
    best, spk = 0.0, None
    for s, e, k in turns:
        ov = min(seg["end"], e) - max(seg["start"], s)
        if ov > best:
            best, spk = ov, k
    return spk


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    audio = await to_wav(await file.read())
    segs = await transcribe_chunks(audio, [])
    return {"text": "".join(s["text"] for s in segs).strip(),
            "duration": len(audio) / SR, "segments": len(segs)}


@app.post("/api/transcribe_diarized")
async def transcribe_diarized(file: UploadFile = File(...)):
    audio = await to_wav(await file.read())
    turns = diarize(audio)
    names = recognize(audio, turns)
    segs = await transcribe_chunks(audio, turns)
    for s in segs:
        k = assign_speaker(s, turns)
        s["speaker"] = names.get(k) or (f"speaker_{k:02d}" if k is not None else None)
        sl = audio[int(s["start"] * SR):int(s["end"] * SR)]
        s["prosody"] = prosody(sl) if len(sl) else None
    return {"text": "".join(s["text"] for s in segs).strip(),
            "duration": len(audio) / SR, "segments": segs}


@app.post("/api/enroll")
async def enroll(name: str = Form(...), file: UploadFile = File(...)):
    emb = embed(await to_wav(await file.read()))
    if name in VP:
        MGR.remove(name)
    MGR.add(name, emb)
    VP[name] = emb.tolist()
    json.dump(VP, open(VOICEPRINTS_FILE, "w"))
    return {"enrolled": name, "total": MGR.num_speakers}


@app.get("/api/voiceprints")
def voiceprints():
    return {"names": list(VP)}


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
