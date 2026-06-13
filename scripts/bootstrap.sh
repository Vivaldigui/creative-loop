#!/usr/bin/env bash
# Creative Loop — Bootstrap script (Linux / macOS)
#
# What this does:
#   1. Validates prerequisites (Python 3.12+, Node 20+)
#   2. Creates .env from .env.example if missing, generates keys
#   3. Creates Python venv and installs deps
#   4. Optionally starts Postgres + Redis via Docker
#   5. Runs Alembic migrations
#   6. Loads fictitious seed data
#
# Usage:
#   bash scripts/bootstrap.sh
#   bash scripts/bootstrap.sh --skip-docker   # assume infra already running
#   bash scripts/bootstrap.sh --skip-seed     # skip seed
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$ROOT/apps/api"
WEB_DIR="$ROOT/apps/web"

SKIP_DOCKER=false
SKIP_SEED=false

for arg in "$@"; do
  case $arg in
    --skip-docker) SKIP_DOCKER=true ;;
    --skip-seed)   SKIP_SEED=true ;;
  esac
done

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   Creative Loop — Bootstrap                  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── 1. Prerequisites ───────────────────────────────────────────────
echo "[1/7] Checking prerequisites..."

if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found. Install Python 3.12+ first."
  exit 1
fi
echo "  Python: $(python3 --version)"

if ! command -v node &>/dev/null; then
  echo "ERROR: node not found. Install Node 20+ from https://nodejs.org"
  exit 1
fi
echo "  Node: $(node --version)"

HAS_DOCKER=false
if command -v docker &>/dev/null; then HAS_DOCKER=true; fi

if [[ "$HAS_DOCKER" == "false" && "$SKIP_DOCKER" == "false" ]]; then
  echo "[!] Docker not found — assuming Postgres+Redis are already running."
  SKIP_DOCKER=true
fi

# ── 2. .env setup ──────────────────────────────────────────────────
echo "[2/7] Configuring environment..."

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "  .env created."

  echo "  Generating SECRET_KEY and ENCRYPTION_KEY..."
  python3 "$ROOT/scripts/gen_keys.py" | while IFS= read -r line; do
    if [[ "$line" =~ ^(SECRET_KEY|ENCRYPTION_KEY)=(.+)$ ]]; then
      varname="${BASH_REMATCH[1]}"
      varval="${BASH_REMATCH[2]}"
      # Replace PREENCHER_ placeholder
      sed -i "s|^${varname}=PREENCHER_.*$|${varname}=${varval}|" "$ROOT/.env"
      echo "  Set $varname"
    fi
  done
  echo "  [!] Review .env — fill in API keys when ready for real providers."
else
  echo "  .env already exists — skipping."
fi

# ── 3. Python venv + deps ──────────────────────────────────────────
echo "[3/7] Installing Python dependencies..."

if [[ ! -d "$API_DIR/.venv" ]]; then
  python3 -m venv "$API_DIR/.venv"
fi
source "$API_DIR/.venv/bin/activate"
pip install -e "$API_DIR[dev]" --quiet
echo "  Done."

# ── 4. Node deps ───────────────────────────────────────────────────
echo "[4/7] Installing Node.js dependencies..."
if [[ ! -d "$WEB_DIR/node_modules" ]]; then
  npm install --prefix "$WEB_DIR" --silent
fi
echo "  Done."

# ── 5. Infra (Postgres + Redis) ────────────────────────────────────
if [[ "$SKIP_DOCKER" == "false" && "$HAS_DOCKER" == "true" ]]; then
  echo "[5/7] Starting Postgres + Redis via Docker..."
  docker compose -f "$ROOT/docker-compose.yml" up -d postgres redis

  echo "  Waiting for Postgres..."
  for i in $(seq 1 30); do
    if docker compose -f "$ROOT/docker-compose.yml" ps postgres 2>/dev/null | grep -q "healthy"; then
      break
    fi
    sleep 2
  done
  echo "  Postgres ready."
else
  echo "[5/7] Skipping Docker infra."
fi

# ── 6. Migrations ──────────────────────────────────────────────────
echo "[6/7] Running Alembic migrations..."
pushd "$API_DIR" > /dev/null
alembic upgrade head
popd > /dev/null

# ── 7. Seed ────────────────────────────────────────────────────────
if [[ "$SKIP_SEED" == "false" ]]; then
  echo "[7/7] Loading fictitious seed data..."
  python "$ROOT/scripts/seed.py"
else
  echo "[7/7] Skipping seed."
fi

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  Bootstrap complete!                                 ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Start the full stack:                               ║"
echo "║    bash scripts/run-local.sh                        ║"
echo "║                                                      ║"
echo "║  API:   http://localhost:8000                        ║"
echo "║  Docs:  http://localhost:8000/docs                   ║"
echo "║  Web:   http://localhost:3000                        ║"
echo "║                                                      ║"
echo "║  Login: admin@demo.example / demo1234               ║"
echo "║  [FICTITIOUS credentials — development only]        ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
