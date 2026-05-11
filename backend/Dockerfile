# ============================================
# AI Journalist — Backend (FastAPI + Uvicorn)
# ============================================
# Build context must be the project ROOT (../)
# so we can access both backend/ and docs/
# ============================================

FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (cached layer)
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy backend source code
COPY backend/__init__.py /app/backend/__init__.py
COPY backend/app.py /app/backend/app.py
COPY backend/prompts.py /app/backend/prompts.py
COPY backend/ingest_data.py /app/backend/ingest_data.py
COPY backend/validate_loop.py /app/backend/validate_loop.py
COPY backend/.env.example /app/backend/.env.example

# Copy knowledge corpus (needed for ingestion pipeline)
COPY docs/ /app/docs/

EXPOSE 9120

# Health check — hits FastAPI's built-in OpenAPI endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9120/openapi.json')" || exit 1

# Start the server
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "9120"]
