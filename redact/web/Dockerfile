# build from repo root:  docker build -f redactbench/Dockerfile -t ghcr.io/amiller/redactbench:latest .
FROM python:3.10-slim
WORKDIR /app
COPY redactbench/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY marketplace/llm.py llm.py
COPY redactbench/app.py app.py
COPY redactbench/static/ static/
COPY samples/*.txt samples/*.strike.json samples/
COPY samples/redaction-skill/SKILL.md SKILL.md
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
