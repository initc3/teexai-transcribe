FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium xvfb python3 espeak-ng ffmpeg ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY bot.html bot.js pcm-worklet.js entrypoint.sh /srv/
RUN chmod +x /srv/entrypoint.sh
WORKDIR /srv
ENTRYPOINT ["/srv/entrypoint.sh"]
