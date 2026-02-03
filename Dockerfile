# ─────────────────────────────────────────────
# japanese-ocr-pipeline
# ─────────────────────────────────────────────
# Build:   docker build -t japanese-ocr .
# Run:     docker run --env-file .env \
#            -v $(pwd)/input:/app/input \
#            -v $(pwd)/output:/app/output \
#            -v $(pwd)/logs:/app/logs \
#            japanese-ocr
# ─────────────────────────────────────────────

FROM python:3.12-slim AS base

# ── system deps (Poppler for pdf2image) ───────
RUN apt-get update && apt-get install -y --no-install-recommends \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# ── non-root user ─────────────────────────────
RUN groupadd -r appuser && useradd -r -g appuser appuser

# ── working dir ───────────────────────────────
WORKDIR /app

# ── Python deps (cached layer — copied before source) ─
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── application code ──────────────────────────
COPY config/ config/
COPY app/   app/
COPY main.py .

# ── runtime directories (volume mount-points) ─
# Created here so Docker knows they exist even if the host
# volumes are not yet mounted.  Owned by appuser.
RUN mkdir -p input output logs \
    && chown -R appuser:appuser input output logs

# ── drop to non-root ──────────────────────────
USER appuser

# ── default command ───────────────────────────
# Secrets arrive via --env-file or -e at run time — never baked in.
CMD ["python", "main.py"]