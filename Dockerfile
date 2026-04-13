# ─── Builder stage: resolve and cache wheels ────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt gunicorn


# ─── Runtime stage ───────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

COPY --from=builder /install /usr/local

COPY . .

# Pre-create volume-mounted directories so the bind mount works on first run
RUN mkdir -p data/models

# Make the entrypoint script executable
RUN chmod +x scripts/entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOCAL_DB_PATH=/app/data/transactiq.db \
    MODEL_DIR=/app/data/models

EXPOSE 5000 8501

ENTRYPOINT ["scripts/entrypoint.sh"]

# Default command runs the production API server.
# Override via docker compose `command:` to run the Streamlit dashboard.
CMD ["gunicorn", "--workers", "2", "--timeout", "120", "--bind", "0.0.0.0:5000", "app.api:app"]
