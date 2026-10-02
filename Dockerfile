FROM python:3.11-slim

# Runtime libs needed by OpenCV (headless) and ONNX Runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Make sure runtime folders exist even if .gitkeep files were not committed
RUN mkdir -p static/uploads static/results rag_docs

# Render provides $PORT (default 10000). 1 worker is required because the
# BM25 document index lives in memory (rag.py); threads handle concurrency.
EXPOSE 10000
CMD gunicorn -b 0.0.0.0:${PORT:-10000} -w 1 --threads 4 --timeout 120 app:app
