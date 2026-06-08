FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl bzip2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# diarization models baked into the image (covered by CVM attestation, fetched at build only)
RUN mkdir -p models \
 && curl -sL https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2 \
    | tar xj -C /tmp \
 && mv /tmp/sherpa-onnx-pyannote-segmentation-3-0/model.onnx models/segmentation.onnx \
 && rm -rf /tmp/sherpa-onnx-pyannote-segmentation-3-0 \
 && curl -sL -o models/embedding.onnx \
    https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/wespeaker_en_voxceleb_resnet34_LM.onnx

COPY app.py .
COPY static/ static/

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
