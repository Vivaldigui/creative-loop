# Creative Loop — Operations Runbook

---

## Service overview

| Service | Port | Role |
|---------|------|------|
| FastAPI (uvicorn) | 8000 | REST API, auth, business logic |
| Next.js | 3000 | Web frontend |
| Celery worker | — | Async tasks (analysis, generation, publish) |
| Celery beat | — | Scheduled tasks (reports, reconciliation) |
| Redis | 6379 | Celery broker + result backend |
| PostgreSQL (prod) / SQLite (dev) | 5432 / file | Persistence |

---

## Starting services

### Local development (SQLite + Redis in Docker)
```bash
# Start all services
./scripts/run-local.sh

# API only (no worker/beat)
./scripts/run-local.sh --api-only

# Web only
./scripts/run-local.sh --web-only

# API + worker (no beat)
./scripts/run-local.sh --no-beat
```

### Docker Compose (full stack)
```bash
# Build and start everything
docker compose up --build

# Start without rebuilding
docker compose up

# Background
docker compose up -d

# Tear down (keep volumes)
docker compose down

# Tear down + wipe data
docker compose down -v
```

### Individual containers
```bash
docker compose up api
docker compose up worker
docker compose up beat
docker compose up web
```

---

## Health checks

```bash
# API health
curl http://localhost:8000/healthz

# Celery worker ping (from within container or with broker access)
celery -A app.worker.celery_app inspect ping

# Redis
redis-cli ping   # expects: PONG

# Check task queue depth
celery -A app.worker.celery_app inspect active_queues
```

---

## Database operations

### Run migrations
```bash
cd apps/api

# Apply all pending migrations
DATABASE_DRIVER=sqlite DATABASE_URL=sqlite+aiosqlite:///./creative_loop.db \
  python -m alembic upgrade head

# Check current migration version
python -m alembic current

# See migration history
python -m alembic history --verbose
```

### Create new migration (after model changes)
```bash
cd apps/api
python -m alembic revision --autogenerate -m "describe_your_change"
# Review the generated file in migrations/versions/ before applying
```

### Seed demo data
```bash
# From repo root
DATABASE_DRIVER=sqlite DATABASE_URL=sqlite+aiosqlite:///./apps/api/creative_loop.db \
  python scripts/seed.py
```

---

## Celery task management

### List registered tasks
```bash
celery -A app.worker.celery_app inspect registered
```

### Monitor active tasks
```bash
celery -A app.worker.celery_app inspect active
```

### Purge all queued tasks (CAREFUL)
```bash
celery -A app.worker.celery_app purge
```

### Scheduled tasks (beat)
Beat schedule is defined in `app/worker/celery_app.py`. Key schedules:
- `daily-report`: runs at `DAILY_REPORT_HOUR` (default: 8am `America/Sao_Paulo`)
- `weekly-report`: runs at `WEEKLY_REPORT_DAY` (default: Monday)
- `meta-reconciliation`: reconciles DRY_RUN published ads

---

## Safety protocol

### Two-flag interlock for Meta writes
Real Meta API calls require **both** flags:
```env
DRY_RUN=false
META_WRITE_ENABLED=true
```

In development, **always** keep:
```env
DRY_RUN=true
META_WRITE_ENABLED=false
```

### Emergency pause
If live ads need to be paused immediately:
```bash
# Via API (requires admin token)
curl -X POST http://localhost:8000/publish/emergency-pause \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Emergency pause — investigation in progress"}'
```

### Check AuditLog for suspicious activity
```sql
-- Recent high-impact actions
SELECT actor_id, action, entity_type, entity_id, result, created_at
FROM audit_logs
WHERE action IN ('published', 'activated', 'budget_changed')
ORDER BY created_at DESC
LIMIT 50;
```

---

## Monitoring

### Logs
```bash
# API logs (structured JSON via structlog)
docker compose logs -f api

# Worker logs
docker compose logs -f worker

# Beat logs
docker compose logs -f beat
```

### Error patterns to watch
```bash
# 500 errors in API
docker compose logs api | grep '"status":500'

# Celery task failures
docker compose logs worker | grep "FAILURE\|ERROR"

# Meta publish failures
docker compose logs worker | grep "publish_failed\|guard_blocked"
```

---

## Backup and restore

### SQLite (dev)
```bash
cp apps/api/creative_loop.db apps/api/creative_loop.db.bak.$(date +%Y%m%d)
```

### PostgreSQL (prod)
```bash
# Backup
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Restore
psql $DATABASE_URL < backup_20260101.sql
```

---

## Troubleshooting

### API returns 500 on `/reports/daily`
Check if `meta_image_hash` column exists in `published_ads`:
```sql
PRAGMA table_info(published_ads);  -- SQLite
-- Should include meta_image_hash
```
If missing: `python -m alembic upgrade head`

### Celery registers 0 tasks
Verify `app/worker/tasks/__init__.py` imports all submodules:
```python
from . import creative_tasks, experiment_tasks, meta_tasks, publish_task
```
And `celery_app.py` uses `autodiscover_tasks(["app.worker"])`.

### `packages` not importable at runtime
```bash
cd apps/api
pip install -e ".[dev]"
python -c "import packages; print('OK')"
```

### Stale `.pyc` cache after model changes
```bash
find apps/api -name "*.pyc" -delete
find apps/api -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
```

---

## Environment variable reference

See `ENVIRONMENT_MATRIX.md` for the full variable table with defaults and safety notes.
