# Otter Pilot

A minimal Chrome (MV3) extension that hands your logged-in otter.ai session to your
local Copilot app. Otter.ai has no public API, so the app reuses your existing browser
session cookie.

## What it does / privacy

When you click the button, it reads **only** the `sessionid` and `csrftoken` cookies for
`otter.ai`, and POSTs exactly those two values to the onboarding URL you paste. It never
reads any other cookie or any other site, and never sends anything anywhere else.

Request: `POST <onboarding URL>`, `content-type: application/json`,
body `{"sessionid":"…","csrftoken":"…"}`.

## Load unpacked

1. Open `chrome://extensions`
2. Enable **Developer mode** (top right)
3. **Load unpacked** → select this `otter-pilot` folder

## Use

1. Sign into otter.ai in this Chrome profile.
2. In the Copilot web app's **Connections** panel, copy your personalized onboarding URL
   (looks like `http://localhost:8137/onboard/otter?u=<userToken>`).
3. Click the Otter Pilot toolbar icon, paste the URL, click **Send my Otter login**.
4. On success you'll see `✓ connected as <name>`. On failure, the server's error text.
