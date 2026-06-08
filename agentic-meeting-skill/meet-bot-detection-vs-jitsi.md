# Meet Bot Detection vs. The Jitsi Approach

Date: 2026-06-05

Why a Google-Meet browser-bot (the NousResearch `hermes-agent` `plugins/google_meet`
pattern) is the fragile path, and why our self-hosted Jitsi + raw-audio + TEE-ASR design
sidesteps the failure modes structurally rather than incrementally.

## Trigger

A report that the NousResearch hermes `google_meet` plugin doesn't work in practice:
Google's bot detection disconnects the automated browser mid-call. We could not find a
public writeup naming that exact plugin, but the mechanism is well-documented and the
report is consistent with how every browser-automation Meet bot fails.

## The structural trap

recall.ai (who build Meet bots commercially) state it plainly:

> Google does not provide a public API that allows software to join a Meet call and record it.

Every live-meeting approach is therefore automating a consumer web interface designed for
humans, not programmatic access. There are exactly three paths, and all three are
compromised for an agentic, confidential, attestable meeting skill.

### Path 1 — Caption scraping via headless browser (what hermes `google_meet` does)

- Join: Playwright `chromium.launch()` -> `page.goto(url)` -> click join, mute mic / cam,
  wait on selectors for `"Leave call"` / `"You've been admitted"`.
- Capture: inject a `MutationObserver` via `page.evaluate()` over the caption DOM region,
  pull speaker + text, dedup, emit. Buffer in memory -> store.
- Auth: log in once manually, persist the Chrome profile (`auth.json`) as Playwright
  `storageState`.
- Detection reality (verbatim): *"Google doesn't have APIs for bots to join meets (seems
  like they actively try to prevent bots)"* and *"Frequent joins can trigger CAPTCHA."*
  Mitigation is an arms race: rotate credentials, exponential backoff, stealth plugins.
- Fragility: *"Google can change class names or layout at any time"*; captions *"can miss
  cross-talk, mumbling, or multilingual conversation"*; 2FA breaks the login flow.

This is the path the reported disconnection lands on: the automated browser is detectable,
and even when it stays in, the caption-DOM scrape is brittle to UI changes.

### Path 2 — Audio-capture bot (raw tab audio -> ASR)

Higher accuracy than captions, but recall.ai is candid that it is the hard one:
*"capturing system audio reliably is difficult,"* each bot *"runs a full browser process,
which makes scaling expensive in CPU and memory,"* and it still inherits the same
login / CAPTCHA / UI-break fragility. Needs the Xvfb + PulseAudio virtual-sink plumbing
(the same plumbing hermes realtime mode uses to feed OpenAI Realtime into a fake mic).

### Path 3 — Official Google Meet REST API (no bot)

The "legitimate" route, and why it is unusable for a live agent:

- Post-meeting only: *"Transcripts are only available after the meeting ends. Real-time
  streaming isn't available."*
- Restricted OAuth scope `drive.meet.readonly`; a 4-6 week security assessment plus a
  paid independent assessment.
- Only the meeting-space owner or invited participants in the *same Google Workspace* can
  fetch artifacts.
- Latency 7-41 min after the meeting; timestamps only every 5 min.

### Accuracy ranking (recall.ai measurement)

Meet API 85.71% > ASR bot 83.09% > caption scrape 82.04%. The easy path (caption scrape)
is also the least accurate, on top of being the most fragile.

## Why Jitsi steps out of all three

1. No adversary. Jitsi is open-source and self-hosted; the bot joins as a first-class
   participant via the Jitsi SDK / `lib-jitsi-meet`, on a server we own. There is no
   detector to evade, so the CAPTCHA / fingerprint arms race does not exist.
2. Raw audio, not scraped captions. We take the actual media stream into
   `teexai-transcribe`, so transcript quality and the ASR model are ours to control, and
   nothing depends on a caption DOM that Google can change or gate.
3. Stable contract. Jitsi's join/media APIs are a real interface we build against; the Meet
   caption DOM is an unstable surface that has to be reverse-engineered indefinitely.
4. Attestable + redactable. You cannot attest or redact a transcript scraped out of someone
   else's web UI. Owning the pipeline is a prerequisite for the TEE-ASR + Cue-redaction
   story, not an optional nicety.

## The honest tradeoff

The Meet browser-bot wins on distribution: it meets people where they already are. Our
Jitsi path trades "meet them where they are" for owning the whole pipeline — a distribution
problem, not an engineering trap. For a confidential, attestable meeting agent, owning the
pipeline is the requirement, so the trade is the right one.

## Primary sources

- [recall.ai — building an in-house Google Meet bot](https://www.recall.ai/blog/how-i-built-an-in-house-google-meet-bot)
- [recall.ai — Puppeteer Google Meet bot](https://www.recall.ai/blog/puppeteer-google-meet-bot)
- [recall.ai — getting Meet transcripts programmatically (developer edition)](https://www.recall.ai/blog/how-to-get-transcripts-from-google-meet-developer-edition)
- [recall.ai — open source Google Meet recording](https://www.recall.ai/blog/is-there-open-source-google-meet-recording-software)
- [NousResearch/hermes-agent — plugins/google_meet](https://github.com/NousResearch/hermes-agent/tree/main/plugins/google_meet)
- [ZenRows — avoiding Playwright bot detection](https://www.zenrows.com/blog/avoid-playwright-bot-detection)
