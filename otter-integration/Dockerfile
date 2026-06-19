FROM python:3.10-slim

# libolm: build dep for python-olm (matrix-nio[e2e]) and runtime for E2EE Matrix posting.
RUN apt-get update && apt-get install -y --no-install-recommends libolm-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY otter_session.py otter_sync.py otter_live.py otter_watch.py otter_wake.py ./
COPY otter_web/ otter_web/

# Pod runs the live dashboard with a sealed Otter cookie; transcripts land on /data.
# The Matrix sidecar (E2EE nio client) runs alongside it, tailing /data/matrix_spool and
# keeping its crypto store on /data/nio_store. Both processes share the persistent volume.
ENV OTTER_SESSION=sealed HOST=0.0.0.0 OTTER_OUT=/data/otter

EXPOSE 8137
CMD ["sh", "-c", "python otter_web/matrix_sidecar.py & exec python otter_web/server.py"]
