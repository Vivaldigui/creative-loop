FROM python:3.12-slim

# System deps for Pillow, imagehash, psycopg2-binary compile
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Copy shared packages from repo root first (better layer cache) ──
COPY packages/ ./packages/

# ── Copy API source ─────────────────────────────────────────────────
COPY apps/api/ ./apps/api/
COPY migrations/ ./migrations/
COPY alembic.ini ./alembic.ini

# ── Install Python deps (editable so packages/* is on sys.path) ─────
RUN pip install --no-cache-dir -e "./apps/api"

# ── Working dir for uvicorn / celery (contains app/, alembic.ini) ───
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
