"""Post messages to a Matrix room — the one outbound-to-Matrix path.

Creds from env: MATRIX_HOMESERVER (e.g. https://matrix.org), MATRIX_ROOM (!id:server),
MATRIX_TOKEN (a bot access token). With all three set it posts; with any missing it runs
in dry-run and logs what it would send — the same chrome|sealed split otter_session.py uses,
so local self-test (replay) exercises the full path with no creds. Errors propagate.
"""
import os, time, requests

HS = os.environ.get("MATRIX_HOMESERVER")
ROOM = os.environ.get("MATRIX_ROOM")
TOKEN = os.environ.get("MATRIX_TOKEN")
LIVE = bool(HS and ROOM and TOKEN)


def post(body, html=None):
    if not LIVE:
        print(f"[matrix dry-run] {body}", flush=True)
        return
    txn = str(time.time_ns())
    url = f"{HS}/_matrix/client/v3/rooms/{ROOM}/send/m.room.message/{txn}"
    msg = {"msgtype": "m.notice", "body": body}
    if html:
        msg.update({"format": "org.matrix.custom.html", "formatted_body": html})
    r = requests.put(url, headers={"Authorization": f"Bearer {TOKEN}"}, json=msg, timeout=20)
    r.raise_for_status()
    return r.json()
