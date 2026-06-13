#!/usr/bin/env bash
# Creative Loop — Local runner (Linux / macOS, no Docker required)
#
# Usage:
#   bash scripts/run-local.sh              # full stack
#   bash scripts/run-local.sh --api-only   # API + worker only
#   bash scripts/run-local.sh --web-only   # frontend only
#   bash scripts/run-local.sh --no-worker  # API + frontend, no Celery
#   bash scripts/run-local.sh --migrate    # migrations only
#   bash scripts/run-local.sh --seed       # seed only
#
# Worker/Beat requires Redis on localhost:6379.
#   docker run -d -p 6379:6379 redis:7-alpine
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$ROOT/apps/api"
WEB_DIR="$ROOT/apps/web"

API_ONLY=false
WEB_ONLY=false
NO_WORKER=false
MIGRATE_ONLY=false
SEED_ONLY=false

for arg in "$@"; do
  case $arg in
    --api-only)    API_ONLY=true ;;
    --web-only)    WEB_ONLY=true ;;
    --no-worker)   NO_WORKER=true ;;
    --migrate)     MIGRATE_ONLY=true ;;
    --seed)        SEED_ONLY=true ;;
  esac
done

echo "=== Creative Loop — Local Start ==="

# ── Copy .env ──────────────────────────────────────────────────────
if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "[!] .env created from .env.example."
  echo "    Run 'python scripts/gen_keys.py' and paste SECRET_KEY + ENCRYPTION_KEY into .env."
  echo "    Press Enter to continue after editing .env, or Ctrl+C to abort."
  read -r _
fi

# ── Python venv ────────────────────────────────────────────────────
if [[ ! -d "$API_DIR/.venv" ]]; then
  echo "[*] Creating venv..."
  python3 -m venv "$API_DIR/.venv"
fi
source "$API_DIR/.venv/bin/activate"

echo "[*] Installing Python deps..."
pip install -e "$API_DIR[dev]" --quiet

# ── Migrations ─────────────────────────────────────────────────────
echo "[*] Running Alembic migrations..."
pushd "$API_DIR" > /dev/null
alembic upgrade head
popd > /dev/null

[[ "$MIGRATE_ONLY" == "true" ]] && echo "Done (migrate only)." && exit 0

# ── Seed ───────────────────────────────────────────────────────────
echo "[*] Seeding..."
python "$ROOT/scripts/seed.py"
[[ "$SEED_ONLY" == "true" ]] && echo "Done (seed only)." && exit 0

# ── Check Redis ─────────────────────────────────────────────────────
REDIS_OK=false
if command -v redis-cli &>/dev/null && redis-cli -p 6379 ping &>/dev/null 2>&1; then
  REDIS_OK=true
elif nc -z 127.0.0.1 6379 &>/dev/null 2>&1; then
  REDIS_OK=true
fi

if [[ "$REDIS_OK" == "false" && "$WEB_ONLY" == "false" && "$NO_WORKER" == "false" && "$API_ONLY" == "false" ]]; then
  echo "[!] Redis not detected on :6379 — skipping worker/beat."
  echo "    Start Redis with: docker run -d -p 6379:6379 redis:7-alpine"
  NO_WORKER=true
fi

PIDS=()

# ── Start API ──────────────────────────────────────────────────────
if [[ "$WEB_ONLY" == "false" ]]; then
  echo "[*] Starting API on :8000..."
  pushd "$API_DIR" > /dev/null
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
  PIDS+=($!)
  popd > /dev/null
fi

# ── Start Worker + Beat ─────────────────────────────────────────────
if [[ "$WEB_ONLY" == "false" && "$API_ONLY" == "false" && "$NO_WORKER" == "false" && "$REDIS_OK" == "true" ]]; then
  echo "[*] Starting Celery worker..."
  pushd "$API_DIR" > /dev/null
  celery -A app.worker.celery_app worker --loglevel=info --concurrency=1 &
  PIDS+=($!)
  celery -A app.worker.celery_app beat --loglevel=info &
  PIDS+=($!)
  popd > /dev/null
fi

# ── Start Web ──────────────────────────────────────────────────────
if [[ "$API_ONLY" == "false" ]]; then
  if [[ ! -d "$WEB_DIR/node_modules" ]]; then
    echo "[*] Installing Node deps..."
    npm install --prefix "$WEB_DIR"
  fi
  echo "[*] Starting Next.js on :3000..."
  npm run dev --prefix "$WEB_DIR" &
  PIDS+=($!)
fi

echo ""
echo "=== Services ==="
echo "  API:     http://localhost:8000"
echo "  Docs:    http://localhost:8000/docs"
echo "  Web:     http://localhost:3000"
echo "  Login:   admin@demo.example / demo1234  [FICTITIOUS — dev only]"
echo ""
echo "PIDs: ${PIDS[*]}"
echo "Press Ctrl+C to stop all."

cleanup() { kill "${PIDS[@]}" 2>/dev/null; }
trap cleanup EXIT INT TERM
wait
