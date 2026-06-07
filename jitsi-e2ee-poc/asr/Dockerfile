FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" faster-whisper numpy
# Pre-pull the model so the timed test does no network I/O.
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base', download_root='/models', compute_type='int8')"
COPY server.py /app/server.py
WORKDIR /app
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
