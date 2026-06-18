#!/usr/bin/env python3
"""Instrument a logged-in Otter web session to study its real network calls.

Injects the Chrome otter.ai cookies into a headless Playwright context (no manual
login), navigates the real web app, and records every request to a HAR + a compact
JSON summary of the forward/api/v1 and api.aisense.com calls. Read-only: it watches
what the app does, it doesn't hammer endpoints ourselves.

Usage:
  python3 otter_capture.py            # load my-notes
  python3 otter_capture.py <otid>     # also open that meeting note (to capture text+frame fetches)
"""
import json, sys, time
from pathlib import Path
import browser_cookie3 as bc
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
HAR = HERE / "otter_capture.har"
SUMMARY = HERE / "otter_capture_summary.json"


def main():
    otid = sys.argv[1] if len(sys.argv) > 1 else None
    jar = bc.chrome(domain_name="otter.ai")
    cookies = [{"name": c.name, "value": c.value,
                "domain": c.domain if c.domain.startswith(".") else "." + c.domain.lstrip("."),
                "path": c.path or "/", "secure": True} for c in jar]

    calls = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(record_har_path=str(HAR), record_har_mode="full")
        ctx.add_cookies(cookies)

        def on_req(req):
            if "forward/api/v1" in req.url or "aisense.com" in req.url:
                calls.append({"method": req.method, "url": req.url.split("?")[0],
                              "query": req.url.split("?")[1] if "?" in req.url else "",
                              "post": (req.post_data or "")[:300]})

        page = ctx.new_page()
        page.on("requestfinished", on_req)
        # Otter keeps a live websocket open, so networkidle never fires; load + settle instead.
        page.goto("https://otter.ai/my-notes", wait_until="domcontentloaded", timeout=45000)
        time.sleep(6)
        if otid:
            page.goto(f"https://otter.ai/note/{otid}", wait_until="domcontentloaded", timeout=45000)
            time.sleep(8)
        ctx.close()
        browser.close()

    SUMMARY.write_text(json.dumps(calls, indent=2))
    print(f"captured {len(calls)} api/aisense calls -> {SUMMARY.name}, full HAR -> {HAR.name}")
    seen = []
    for c in calls:
        key = (c["method"], c["url"])
        if key not in seen:
            seen.append(key)
            print(f"  {c['method']:5s} {c['url']}")


if __name__ == "__main__":
    main()
