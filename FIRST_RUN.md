# Creative Loop — First Run Guide

**All API calls are mock by default. No real Meta/Anthropic/OpenAI calls are made.**

---

## Prerequisites

| Tool | Minimum version | Check |
|------|-----------------|-------|
| Python | 3.12 | `python --version` |
| Node.js | 20 | `node --version` |
| Redis | 7 | `redis-cli ping` → `PONG` |
| Docker Desktop | 4.x | `docker --version` |

---

## Step 1 — Bootstrap (one time only)

### Windows (PowerShell)
```powershell
cd C:\path\to\creative-loop
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\bootstrap.ps1
```

### Linux / macOS
```bash
cd /path/to/creative-loop
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh
```

The bootstrap script:
1. Checks prerequisites
2. Creates `.env` from `.env.example` and generates secret keys automatically
3. Installs Python dependencies (`pip install -e ".[dev]"` in `apps/api/`)
4. Installs frontend dependencies (`npm ci` in `apps/web/`)
5. Starts Redis and PostgreSQL via Docker (if Docker is available)
6. Runs Alembic migrations (`alembic upgrade head`)
7. Seeds demo data (fictitious, safe for dev)

---

## Step 2 — Start the application

### Windows
```powershell
.\scripts\run-local.ps1
```

### Linux / macOS
```bash
./scripts/run-local.sh
```

This starts:
- FastAPI backend on http://localhost:8000
- Next.js frontend on http://localhost:3000
- Celery worker (background tasks)
- Celery beat (scheduled tasks) — requires Redis

---

## Step 3 — Login

Open http://localhost:3000 in your browser.

| Field | Value |
|-------|-------|
| Email | `admin@demo.example` |
| Password | `demo1234` |

> These credentials are created by the seed script. They are fictitious and exist only in your local database.

---

## Step 4 — Verify everything is running

```bash
# Health check
curl http://localhost:8000/healthz

# API docs
open http://localhost:8000/docs   # macOS
start http://localhost:8000/docs  # Windows
```

Expected health response:
```json
{
  "status": "ok",
  "version": "0.7.0",
  "dry_run": true,
  "meta_write_enabled": false,
  "require_human_approval": true
}
```

---

## Step 5 — Mock flow walkthrough

This is the complete flow using mock providers (no real API calls).

### 5a. View source ads (Meta mock data)
```
http://localhost:3000/source-ads
```
Demo data: 3 fictitious ads pre-seeded from the mock Meta import.

### 5b. View products
```
http://localhost:3000/products
```
Demo data: "Demo Skincare Product" with a fictitious brand profile.

### 5c. Generate a creative (mock OpenAI)
Navigate to any source ad → "Analyze" → "Generate Creative".
- Analysis uses `MockAnthropicClient` (deterministic, zero HTTP)
- Image generation uses `MockImageClient` (deterministic PNG, zero HTTP)
- No Anthropic or OpenAI API keys required

### 5d. Approve and (DRY_RUN) publish
Navigate to the generated creative → "Approve for Publishing".
The creative goes through:
1. Quality Gate (deterministic checks)
2. Policy Gate (rule-based)
3. Human approval queue (required because `REQUIRE_HUMAN_APPROVAL=true`)
4. **DRY_RUN publish** — logs to AuditLog, zero HTTP to Meta

### 5e. View experiments
```
http://localhost:3000/experiments
```
Demo data: "Background Color Test" experiment with 2 variants.

### 5f. View learnings
```
http://localhost:3000/learnings
```
Demo data: 1 confirmed learning + 1 provisional learning.

---

## Safety switches (always on in dev)

| Variable | Value | Effect |
|----------|-------|--------|
| `DRY_RUN` | `true` | All publish calls are simulated — no Meta API |
| `META_WRITE_ENABLED` | `false` | Second lock on Meta writes |
| `REQUIRE_HUMAN_APPROVAL` | `true` | No automated publishing |
| `MAX_AUTOMATIC_BUDGET_INCREASE_PERCENT` | `0` | No budget changes |

**Do not change these values** unless you have explicitly set up real API credentials and understand the consequences.

---

## Common issues

### `ModuleNotFoundError: No module named 'packages'`
Re-install the API package from the repo root:
```bash
cd apps/api && pip install -e ".[dev]"
```

### `redis.exceptions.ConnectionError`
Start Redis:
```bash
docker run -d -p 6379:6379 redis:7-alpine   # or use scripts/bootstrap
```

### Port already in use
```bash
# Kill whatever is on port 8000
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F
# Linux/macOS:
lsof -ti:8000 | xargs kill -9
```

### Database errors / missing columns
Re-run migrations:
```bash
cd apps/api
DATABASE_DRIVER=sqlite DATABASE_URL=sqlite+aiosqlite:///./creative_loop.db \
  python -m alembic upgrade head
```

---

## Connecting real APIs (when ready)

See `docs/ANTHROPIC_SETUP.md`, `docs/OPENAI_SETUP.md`, and `docs/META_SETUP.md`.

**Never set `META_WRITE_ENABLED=true` without explicit sign-off from your team.**
