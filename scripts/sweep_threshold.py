#!/usr/bin/env python3
"""Sweep the open-set speaker-match threshold (SPEAKER_THRESHOLD) on labeled clips.

So the production threshold is *documented* rather than guessed (PRD acceptance
criterion). Decodes clips with ffmpeg and embeds them with the same wespeaker
model the CVM ships (models/embedding.onnx).

Clip naming: ``<label>__<anything>.wav`` (or ``<label>_<...>``). The label before
the first ``_`` is the person. One clip per label is enrolled (the rest are
genuine trials); pass ``--holdout NAME`` to leave a person unenrolled so their
clips act as imposters and exercise false-accept rate.

    python scripts/sweep_threshold.py path/to/clips --holdout mallory

Reports, per threshold: FRR (genuine rejected), FAR (imposter accepted), and the
misident rate; flags the threshold nearest equal-error (FAR≈FRR).
"""
import argparse
import os
import subprocess
import sys
from collections import defaultdict

import numpy as np
import sherpa_onnx

EMB_MODEL = os.environ.get("EMB_MODEL", "models/embedding.onnx")
SR = 16000


def decode(path: str) -> np.ndarray:
    out = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-i", path,
         "-ar", str(SR), "-ac", "1", "-f", "f32le", "pipe:1"],
        capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype=np.float32)


def label_of(fname: str) -> str:
    return os.path.basename(fname).split("__")[0].split("_")[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips_dir")
    ap.add_argument("--holdout", action="append", default=[],
                    help="label(s) to leave unenrolled (imposters)")
    ap.add_argument("--enroll-per-label", type=int, default=1)
    args = ap.parse_args()

    ext = sherpa_onnx.SpeakerEmbeddingExtractor(
        sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=EMB_MODEL))

    def embed(samples):
        s = ext.create_stream()
        s.accept_waveform(sample_rate=SR, waveform=samples)
        s.input_finished()
        v = np.array(ext.compute(s), dtype=np.float32)
        return v / (np.linalg.norm(v) + 1e-9)

    by_label = defaultdict(list)
    for fn in sorted(os.listdir(args.clips_dir)):
        if fn.lower().endswith((".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac")):
            by_label[label_of(fn)].append(os.path.join(args.clips_dir, fn))
    if not by_label:
        sys.exit("no audio clips found")

    # Enroll centroids, collect genuine + imposter trials.
    centroids = {}
    genuine, imposter = [], []  # (embedding, true_label)
    for label, files in by_label.items():
        embs = [embed(decode(f)) for f in files]
        if label in args.holdout:
            imposter += [(e, label) for e in embs]
            continue
        k = min(args.enroll_per_label, len(embs))
        centroids[label] = np.mean(embs[:k], axis=0)
        genuine += [(e, label) for e in embs[k:]]
    if not centroids:
        sys.exit("every label held out — nothing enrolled")

    names = list(centroids)
    C = np.stack([centroids[n] for n in names])

    def best(emb):  # (score, predicted_label) — cosine to nearest centroid
        sims = C @ emb
        i = int(np.argmax(sims))
        return float(sims[i]), names[i]

    # genuine trial = (score, predicted_label, true_label); imposter = score only
    g = [(*best(e), lbl) for e, lbl in genuine]
    im = [best(e)[0] for e, _ in imposter]

    print(f"enrolled {len(names)} · genuine trials {len(g)} · imposter trials {len(im)}\n")
    print(f"{'thr':>5} {'FRR':>7} {'FAR':>7} {'misID':>7}")
    rows = []
    for thr in [x / 100 for x in range(30, 86, 5)]:
        fr = sum(1 for sc, _, _ in g if sc < thr) / max(1, len(g))
        mis = sum(1 for sc, pred, lbl in g if sc >= thr and pred != lbl) / max(1, len(g))
        fa = (sum(1 for sc in im if sc >= thr) / len(im)) if im else float("nan")
        rows.append((thr, fr, fa, mis))
        print(f"{thr:5.2f} {fr:7.2%} {fa:7.2%} {mis:7.2%}")

    if im:
        eer = min(rows, key=lambda r: abs(r[1] - r[2]))
        print(f"\nsuggested SPEAKER_THRESHOLD ≈ {eer[0]:.2f} "
              f"(FRR {eer[1]:.0%} ≈ FAR {eer[2]:.0%})")
    else:
        print("\n(no imposters — pass --holdout NAME to measure false-accept rate)")


if __name__ == "__main__":
    main()
