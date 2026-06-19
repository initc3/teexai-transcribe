"""Shared Otter session — one auth path for every tool here.

Provider selected by OTTER_SESSION:
  chrome (default) — reuse the Chrome otter.ai login via browser_cookie3 (local).
  sealed           — read OTTER_SESSIONID / OTTER_CSRFTOKEN from the env, the way a
                     TEE pod receives them as sealed secrets (no browser in the enclave).

Everything downstream is identical; only where the cookie comes from differs. That diff
is the whole audit surface between the local run and the hosted/pod run.
"""
import os
import requests

BASE = "https://otter.ai/forward/api/v1/"


def _cookies():
    mode = os.environ.get("OTTER_SESSION", "chrome")
    if mode == "chrome":
        import browser_cookie3 as bc
        jar = {c.name: c.value for c in bc.chrome(domain_name="otter.ai")}
        return {"sessionid": jar["sessionid"], "csrftoken": jar["csrftoken"]}
    if mode == "sealed":
        return {"sessionid": os.environ["OTTER_SESSIONID"], "csrftoken": os.environ["OTTER_CSRFTOKEN"]}
    raise ValueError(f"OTTER_SESSION must be chrome|sealed, got {mode!r}")


def open_session():
    c = _cookies()
    s = requests.Session()
    s.cookies.update(c)
    s.headers.update({"referer": "https://otter.ai/", "user-agent": "Mozilla/5.0"})
    s.uid = s.get(BASE + "user", timeout=30).json()["userid"]
    s.csrf = c["csrftoken"]
    s.media = c  # api.aisense.com assets need sessionid+csrftoken sent explicitly (cross-domain)
    return s
