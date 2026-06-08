#!/usr/bin/env bash
# Download the speaker models into models/ for local dev.
# (The Docker image does the same thing at build time.)
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p models

SEG=https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2
EMB=https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/wespeaker_en_voxceleb_CAM++.onnx

if [ ! -f models/segmentation.onnx ]; then
  echo "↓ segmentation (pyannote 3.0)"
  curl -sL "$SEG" | tar xj -C /tmp
  mv /tmp/sherpa-onnx-pyannote-segmentation-3-0/model.onnx models/segmentation.onnx
  rm -rf /tmp/sherpa-onnx-pyannote-segmentation-3-0
fi

if [ ! -f models/embedding.onnx ]; then
  echo "↓ embedding (wespeaker voxceleb CAM++)"
  curl -sL -o models/embedding.onnx "$EMB"
fi

echo "✓ models ready:"; ls -lh models/*.onnx
