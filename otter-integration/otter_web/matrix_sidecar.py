#!/usr/bin/env python3
"""Persistent E2EE Matrix sender — the sidecar matrix.py enqueues to.

A long-lived matrix-nio[e2e] client (needs libolm). It restores the bot's login with its
persisted device_id, keeps a persistent crypto store on /data (megolm sessions + peer
device keys — losing it drops you into a 'cannot decrypt' hole), and tails the spool dir
matrix.post() writes to: each *.json is room_send()'d to the ENCRYPTED target room in
timestamp order and deleted on success. A sync runs before sending (nio's room_send raises
'No such room' until sync populates client.rooms) and between drains so device keys stay
fresh for megolm key-sharing.

Env: MATRIX_HOMESERVER, MATRIX_ROOM (encrypted room id), MATRIX_TOKEN, MATRIX_DEVICE_ID.
     MATRIX_STORE (crypto store dir), MATRIX_SPOOL (queue dir) — both default under /data.
Errors propagate; a send that returns an error response prints and the file is left in the
spool to retry on the next loop (no fallback, no silent drop).
"""
import asyncio, json, os
from pathlib import Path
from nio import AsyncClient, AsyncClientConfig, RoomSendError

HS = os.environ["MATRIX_HOMESERVER"].rstrip("/")
ROOM = os.environ["MATRIX_ROOM"]
TOKEN = os.environ["MATRIX_TOKEN"]
MXID = os.environ.get("MATRIX_USER", "@otter-copilot-bot:mtrx.shaperotator.xyz")
DEVICE = os.environ["MATRIX_DEVICE_ID"]
ONDATA = os.path.isdir("/data")
STORE = Path(os.environ.get("MATRIX_STORE", "/data/nio_store" if ONDATA else
                            str(Path(__file__).parent / "nio_store")))
SPOOL = Path(os.environ.get("MATRIX_SPOOL", "/data/matrix_spool" if ONDATA else
                            str(Path(__file__).parent / "matrix_spool")))
POLL = float(os.environ.get("MATRIX_POLL", "2"))


async def drain(client):
    for f in sorted(SPOOL.glob("*.json")):
        msg = json.loads(f.read_text())
        resp = await client.room_send(ROOM, "m.room.message", msg,
                                      ignore_unverified_devices=True)
        if isinstance(resp, RoomSendError):
            print(f"[sidecar] send failed for {f.name}: {resp.message}", flush=True)
            return  # leave it (and everything after) for the next loop; preserve order
        print(f"POSTED:{resp.event_id}  ({f.name})", flush=True)
        f.unlink()


async def main():
    STORE.mkdir(parents=True, exist_ok=True)
    SPOOL.mkdir(parents=True, exist_ok=True)
    client = AsyncClient(HS, MXID, device_id=DEVICE, store_path=str(STORE),
                         config=AsyncClientConfig(encryption_enabled=True, store_sync_tokens=True))
    client.restore_login(user_id=MXID, device_id=DEVICE, access_token=TOKEN)
    await client.sync(timeout=0, full_state=True)  # populate client.rooms + crypto state
    print(f"[sidecar] live as {MXID}/{DEVICE} -> {ROOM} (encrypted={client.rooms[ROOM].encrypted})", flush=True)
    try:
        while True:
            await drain(client)
            await client.sync(timeout=int(POLL * 1000), full_state=False)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
