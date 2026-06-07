FROM python:3.11-slim
RUN pip install --no-cache-dir requests
COPY run.py /app/run.py
WORKDIR /app
CMD ["python", "run.py"]
