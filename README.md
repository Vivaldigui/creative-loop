# Creative Loop

AI-powered platform that closes the ad creative cycle: import historical ads → analyze with Claude → generate versioned prompts → generate images (OpenAI) → quality/policy gates → human approval → simulate publish (Meta DRY_RUN) → collect metrics → register learnings → next experiment round.

> **Phase 7 status:** Experiments, evaluations, learning lifecycle, and next-round suggestions — EXPLORATORY/CONTROLLED experiments with single-variable isolation, conservative Beta-Binomial evaluator (never declares a winner without sufficient data + maturation), append-only `ExperimentEvaluation`, advisory `OptimizationDecision` (never changes budget), `Learning` lifecycle (always starts `provisional`; confirmation requires human review), diversity-scored `ExperimentSuggestion` (`auto_image_generation: False`, `pending_approval`), idempotent Celery metric-collection + anomaly-detection tasks, daily/weekly reports, all Beat schedules in `America/Sao_Paulo`. **No auto fine-tuning, no auto image generation, no auto budget changes. 422 tests passing.**
>
> Earlier phases: Phase 6 real Meta publish (two-flag interlock, all ads PAUSED, manual owner-only activation, emergency pause); Phase 5 DRY_RUN publish simulation; Phase 4 OpenAI image generation + quality/policy gates + approval; Phase 3 Claude analysis + prompt engine; Phase 2 Meta read-only import; Phase 1 MVP vertical flow.

---

## Quick start (local, no Docker required)

> **New here?** See [FIRST_RUN.md](FIRST_RUN.md) for a step-by-step guide including the one-command bootstrap.
>
> **Free hosting:** See [docs/DEPLOYMENT_FREE.md](docs/DEPLOYMENT_FREE.md) for the beginner-friendly Vercel + Render + Neon + R2 setup.

### Prerequisites
- Python 3.12+, Node.js 20+, Redis 7

### Bootstrap (one command)
```bash
# Windows
.\scripts\bootstrap.ps1

# Linux / macOS
./scripts/bootstrap.sh
```

### Or manually

```bash
# Backend
cd apps/api
pip install -e ".[dev]"

# Configure env (bootstrap does this automatically)
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"     # → SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # → ENCRYPTION_KEY

# Migrations (SQLite by default)
python -m alembic upgrade head

# Seed demo data
cd ../.. && python scripts/seed.py

# Start API
cd apps/api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs · Health: http://localhost:8000/healthz

### Frontend

```bash
cd apps/web
npm ci
npm run dev
```

Open http://localhost:3000 and log in with `admin@demo.example` / `demo1234`.

---

## Docker Compose (requires Docker Desktop)

```bash
cp .env.example .env
# Fill in SECRET_KEY and ENCRYPTION_KEY as above
docker compose up --build
```

Services: `api` (8000), `web` (3000), `worker`, `beat`, `postgres`, `redis`.

---

## Project structure

```
creative-loop/
├─ apps/
│  ├─ api/         FastAPI backend (SQLAlchemy 2, Alembic, Pydantic v2)
│  ├─ worker/      Celery worker + Beat scheduler
│  └─ web/         Next.js 15 frontend (App Router, TypeScript)
├─ packages/
│  ├─ anthropic_client/     Analysis client (mock + real)
│  ├─ openai_image_client/  Image generation client (mock + real)
│  ├─ meta_client/          Meta Marketing API client (read + write/publish)
│  ├─ policy_engine/        Regex-based ad policy checker
│  ├─ quality_engine/       Image quality gate
│  ├─ prompt_engine/        Prompt builder + versioning
│  ├─ storage/              Local (HMAC signed URLs) + S3 backends
│  ├─ analytics_engine/     Beta-Binomial stats + winsorized aggregation (no scipy)
│  └─ experiment_engine/    Mode guards + conservative evaluator + diversity scorer
├─ migrations/              Alembic migrations
├─ scripts/                 seed.py, helpers
├─ docs/                    Spec and setup guides
└─ docker-compose.yml
```

---

## Running tests

```bash
cd apps/api
pytest tests/ -q --tb=short
```

422 tests, 7 skipped — all use in-memory SQLite, no external services needed.

## Lint

```bash
ruff check apps/api/ packages/
ruff format apps/api/ packages/
```

---

## Security notes

- All secrets in `.env` only — never committed.
- `SECRET_KEY` and `ENCRYPTION_KEY` must be generated per-environment.
- `DRY_RUN=true` by default — no real Meta writes.
- `REQUIRE_HUMAN_APPROVAL=true` by default — approval required before any publish.
- No financial action without `MAX_DAILY_SPEND` defined.
- All credentials stored Fernet-encrypted at rest.
- JWT in httpOnly SameSite cookie — never exposed to JavaScript.

See [SECURITY.md](SECURITY.md) for the full security model, [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md) for ops procedures, [ENVIRONMENT_MATRIX.md](ENVIRONMENT_MATRIX.md) for all environment variables, and [docs/EXPERIMENTATION.md](docs/EXPERIMENTATION.md) for the experiment/learning lifecycle.

---

## Provider flags

| Env var | Values | Default |
|---|---|---|
| `ANTHROPIC_PROVIDER` | `mock`, `real` | `mock` |
| `IMAGE_PROVIDER` | `mock`, `openai` | `mock` |
| `META_PROVIDER` | `mock`, `real` | `mock` |
| `DRY_RUN` | `true`, `false` | `true` |
| `META_WRITE_ENABLED` | `true`, `false` | `false` |

Switch to `real` + supply the corresponding API key to use live providers. Real Meta **writes** additionally require the two-flag interlock: `DRY_RUN=false` **and** `META_WRITE_ENABLED=true`.

---

## Phase roadmap

| Phase | Description | Status |
|---|---|---|
| 1 | MVP vertical flow (all mock, DRY_RUN) | **Complete** |
| 2 | Meta read-only import | **Complete** |
| 3 | Real Claude analysis + full prompt engine | **Complete** |
| 4 | Real OpenAI image generation + quality gate | **Complete** |
| 5 | Full DRY_RUN publish with payload validation | **Complete** |
| 6 | Real Meta publish (PAUSED by default) | **Complete** |
| 7 | Experiments + learnings + next round | **Complete** |
