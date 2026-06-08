# PRD: Speaker identification via enrolled voiceprints (in-CVM)

## Problem

Diarization (`/api/transcribe_diarized`) clusters unknown voices *within a single
recording*. Three consequences fall out of that being an offline, global operation:

- Labels are anonymous (`speaker_00`, `speaker_01`) — no identity.
- Labels are only stable once the whole recording is processed, so the UI can only
  show them at **Stop**, not live.
- Labels are not consistent across recordings: `speaker_00` in one file is unrelated
  to `speaker_00` in the next.

## Goal

Identify *known* people by matching speech against **enrolled per-person embedding
vectors**, so labels are real names, stable from the first chunk, and consistent
across sessions. Keep diarization for turn boundaries and unknown speakers.

## Why this is the right tool

Identification is per-segment and stateless: `extractor → embedding →
manager.search(embedding, threshold) → name`. No global clustering, so it can run
incrementally (live) and gives stable labels immediately. We already ship the exact
model — the wespeaker embedding extractor (`models/embedding.onnx`) — and
`sherpa_onnx.SpeakerEmbeddingManager` is a built-in enrollment store
(`add` / `search` / `verify` / `remove`).

## Design (hybrid — diarize, then name)

1. Diarize to get coherent speaker turns (unchanged).
2. For each cluster, embed its longest turn → `MGR.search(emb, THR)`.
3. Above threshold → real name; below → fall back to `speaker_NN` (unknown).
4. Live mode (future): skip clustering, identify each chunk's segments directly.
5. Online refinement: average new high-confidence segments into a person's centroid
   so the voiceprint sharpens over time ("building up the vector").

## API

- `POST /api/enroll` — `name` + `file` → embedding → `MGR.add`, persist voiceprint.
- `GET  /api/voiceprints` — list enrolled names.
- `POST /api/transcribe_diarized` — segments carry the resolved name when matched.

## TEE / privacy

Voiceprints are biometric identifiers. They are computed and matched **inside the
CVM** and must be **sealed to the enclave** — never leaving in cleartext. This is a
stronger privacy story than the current pipeline (where audio is forwarded to near.ai
for ASR): voiceprint enrollment and matching never leave the TEE.

## Open questions

- **Threshold (`THR`)**: tune on real + synthetic pairs; pick the open-set bar that
  balances false matches vs. missed identities.
- **Sealed storage**: current prototype writes `voiceprints.json` to the container
  filesystem — ephemeral and lost on redeploy. Move to a dstack/Phala persistent
  encrypted volume or sealing key. (Requirement, not optional, before this is real.)
- **Unknown handling**: how to present `speaker_NN` unknowns alongside named ones.
- **Enroll UX**: who enrolls, how many seconds of reference audio, re-enroll flow.

## Out of scope

- Overlapping / cross-talk speech.
- Cross-lingual robustness (model is English/voxceleb-trained).
- The prosody (`f0`/`rms`) redaction-prior fields are a separate experiment.

## Status

Prototype exists in `app.py`: `SpeakerEmbeddingExtractor`,
`SpeakerEmbeddingManager`, `embed()`, `recognize()`, `/api/enroll`,
`/api/voiceprints`, and name resolution in `transcribe_diarized`. Remaining work
below.

## Acceptance criteria

- [ ] Enroll a person from a reference clip; `transcribe_diarized` labels their turns
      with that name on a separate recording.
- [ ] Unmatched speakers fall back to `speaker_NN`; no false names above threshold on
      a held-out non-enrolled voice.
- [ ] Voiceprints persist across CVM redeploy via sealed storage (not container fs).
- [ ] Threshold chosen from a documented sweep, not a guess.
- [ ] Enroll UI in the demo page; enrolled names render on the transcript.
- [ ] (Stretch) Live per-chunk identification with stable labels from chunk 1.
