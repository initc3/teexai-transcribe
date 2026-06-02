import os
import json
import asyncio
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

API_KEY = os.environ["NEAR_API_KEY"]
BASE = "https://cloud-api.near.ai/v1"
NOTES_FILE = "notes.json"

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


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    audio = await to_ogg(await file.read())
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{BASE}/audio/transcriptions",
            headers=headers(),
            files={"file": ("audio.ogg", audio, "audio/ogg")},
            data={"model": "openai/whisper-large-v3"},
        )
    return JSONResponse(r.json(), status_code=r.status_code)


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
            msg = r.json()["choices"][0]["message"]
            messages.append(msg)
            calls = msg.get("tool_calls")
            if not calls:
                return {"reply": msg.get("content", ""), "messages": messages}
            for c in calls:
                result = run_tool(c["function"]["name"],
                                  json.loads(c["function"]["arguments"] or "{}"))
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": str(result)})
    return {"reply": "(stopped: too many tool steps)", "messages": messages}


@app.get("/")
def index():
    return FileResponse("static/index.html")
