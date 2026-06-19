FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY otter_session.py otter_sync.py otter_live.py otter_watch.py ./
COPY otter_web/ otter_web/

# Pod runs the live dashboard with a sealed Otter cookie; transcripts land on /data.
ENV OTTER_SESSION=sealed HOST=0.0.0.0 OTTER_OUT=/data/otter

EXPOSE 8137
CMD ["python", "otter_web/server.py"]
