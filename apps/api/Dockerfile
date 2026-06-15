# PeerForge API — FastAPI backend
#
# Same image serves both Railway services:
#   API service start command:    uvicorn src.main:app --host 0.0.0.0 --port $PORT
#   Worker service start command: celery -A src.celery_app worker --loglevel=info -Q celery,materials,preflight --concurrency=2
#
# Single-instance free-tier deployments can skip the worker entirely by
# setting CELERY_TASK_ALWAYS_EAGER=true (tasks run inside the API process).

FROM python:3.12-slim

WORKDIR /app

# System dependencies for psycopg2 and document extraction
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
