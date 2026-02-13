# ─────────────────────────────────────────────
# japanese-ocr-translator (unified pipeline)
# ─────────────────────────────────────────────
# Build:   docker build -t japanese-ocr .
# Run:     docker compose up
# ─────────────────────────────────────────────

FROM python:3.12-slim AS base

# ── System deps (Poppler for pdf2image) ───────
RUN apt-get update && apt-get install -y --no-install-recommends \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root user ─────────────────────────────
RUN groupadd -r appuser && useradd -r -g appuser appuser

# ── Working dir ───────────────────────────────
WORKDIR /app

# ── Python deps ───────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────
COPY config/ config/
COPY app/   app/
COPY main.py .

# ── Runtime directories ───────────────────────
RUN mkdir -p input output/images logs \
    && chown -R appuser:appuser input output logs

# ── Drop to non-root ──────────────────────────
USER appuser

# ── Default command ───────────────────────────
CMD ["python", "main.py"]