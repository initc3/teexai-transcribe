# build from repo root:  docker build -f redactbench/bun/Dockerfile -t ghcr.io/amiller/redactbench:latest .
FROM oven/bun:1
WORKDIR /app
COPY redactbench/bun/package.json redactbench/bun/bun.lock ./
RUN bun install --frozen-lockfile
COPY redactbench/bun/model.ts redactbench/bun/data.ts redactbench/bun/redact.tsx redactbench/bun/server.ts redactbench/bun/tsconfig.json ./
COPY redactbench/bun/static/ static/
COPY samples/*.txt samples/*.strike.json samples/
COPY samples/redaction-skill/SKILL.md SKILL.md
ENV SAMPLES_DIR=/app/samples SKILL_PATH=/app/SKILL.md
EXPOSE 8000
CMD ["bun", "server.ts"]
