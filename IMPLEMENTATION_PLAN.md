# Implementation Plan — Creative Loop

## Phase 1: MVP vertical flow (COMPLETE)

All tasks in Phase 1 have been implemented and verified.

### Deliverables

| Task | Description | Status |
|---|---|---|
| F1-01 | Monorepo skeleton (pyproject.toml, package.json, .gitignore, docker-compose.yml) | ✓ Done |
| F1-02 | Docker Compose + .env.example (all secrets as PREENCHER_* placeholders) | ✓ Done |
| F1-03 | FastAPI app factory, config (pydantic-settings), db async (SQLAlchemy 2), /healthz, /readyz | ✓ Done |
| F1-04 | Auth: JWT (HS256, httpOnly cookie), Argon2 password hashing, RBAC (owner/admin/viewer), org scoping | ✓ Done |
| F1-05 | All 17 models + Alembic async migration (portable UUID/JSONB types for SQLite + PostgreSQL) | ✓ Done |
| F1-06 | Mock packages: anthropic_client, openai_image_client (Pillow PNG), meta_client, policy_engine, quality_engine, prompt_engine | ✓ Done |
| F1-07 | All Phase 1 endpoints (auth, products, brand, source-ads, prompts, creatives, publish, healthz) | ✓ Done |
| F1-08 | Seed script: 1 org, 1 user, 5 source ads + snapshots, 3 analyses, 3 prompt versions, 4 creatives, 1 experiment | ✓ Done |
| F1-09 | Celery worker stub (eager mode for Phase 1) | ✓ Done |
| F1-10 | Next.js frontend: Login, Dashboard, Products, Ad Library, Ad Detail (full flow), Approvals | ✓ Done |
| F1-11 | Tests: 25 tests passing — auth, org isolation, prompt versioning, DRY_RUN, policy checks, vertical E2E | ✓ Done |
| F1-12 | CI: GitHub Actions (ruff + mypy + pytest + eslint + tsc + next build) | ✓ Done |
| F1-13 | Docs: README, ARCHITECTURE, SECURITY, IMPLEMENTATION_PLAN | ✓ Done |

### Test results

```
25 passed, 2 warnings
```

### Lint results

```
ruff: All checks passed!
eslint: No ESLint warnings or errors
tsc: No errors
next build: 9 routes compiled
```

### Security constraints in effect

- `DRY_RUN=true` — no real Meta writes
- `REQUIRE_HUMAN_APPROVAL=true` — approval required before publish
- `MAX_DAILY_SPEND` empty → publish blocked until defined
- All mock providers (no real API calls, no cost)
- All seed data marked `is_fictitious=True`

---

## Phase 2: Meta Read-Only Import + Historical Library (COMPLETE)

### Deliverables

| Task | Description | Status |
|---|---|---|
| F2-01 | `MetaGraphTransport` — GET-only, appsecret_proof, retry/backoff, rate-limit header monitoring | ✓ Done |
| F2-02 | `MetricNormalizer` — priority-ordered action_type mapping, null semantics, ROAS reported/derived | ✓ Done |
| F2-03 | Full `MetaClientProtocol` — iter_campaigns, iter_adsets, iter_ads, iter_ad_images, iter_insights | ✓ Done |
| F2-04 | `MockMetaClient` — fixture-based (7 JSON fixtures), async generators | ✓ Done |
| F2-05 | `RealMetaClient` — transport-backed, monthly insight chunking (GET only) | ✓ Done |
| F2-06 | Provider factory — `META_PROVIDER=mock\|real` env switch | ✓ Done |
| F2-07 | 6 new ORM models: AdAccount, SourceCampaign, SourceAdSet, SourceCreative, SourceAsset, MetaSyncRun | ✓ Done |
| F2-08 | SourceAd + PerformanceSnapshot extended with Phase 2 fields (nullable, backward-compatible) | ✓ Done |
| F2-09 | Alembic migration `b4c8f2a1e9d3` — CREATE 6 tables + ALTER 2 tables + unique constraints | ✓ Done |
| F2-10 | `MetaImportService` — full orchestration with upsert idempotency, token redaction, budget conversion | ✓ Done |
| F2-11 | Celery tasks: sync_meta_history, sync_meta_incremental, dispatch_meta_incremental_syncs (Beat hourly) | ✓ Done |
| F2-12 | Sync router: POST /sync/meta/history, /incremental, GET /sync/meta/runs, /runs/{id} | ✓ Done |
| F2-13 | Extended GET /source-ads with filters (label, source, objective, status, is_fictitious, pagination) | ✓ Done |
| F2-14 | GET /source-ads/{id}/insights — time series endpoint | ✓ Done |
| F2-15 | Extended GET /metrics with date/source filters; new GET /metrics/top-ads | ✓ Done |
| F2-16 | Frontend: /integrations page (provider test, accounts, sync history, trigger buttons) | ✓ Done |
| F2-17 | Frontend: /metrics page (KPI cards, top-ads table with metric selector) | ✓ Done |
| F2-18 | Frontend: /ads updated with filter bar, source/fictitious badges, pagination | ✓ Done |
| F2-19 | Frontend: /ads/[id] updated with insights time series, creative/adset context, raw response viewer | ✓ Done |
| F2-20 | Unit tests: test_meta_normalize.py (priority, nulls, ROAS, dirty fixture) | ✓ Done |
| F2-21 | Unit tests: test_meta_transport.py (auth error, retry, rate-limit, pagination) | ✓ Done |
| F2-22 | Integration tests: test_meta_sync.py (full flow, idempotency, org isolation, RBAC, lifecycle) | ✓ Done |
| F2-23 | Docs: docs/META_SETUP.md, docs/METRICS_NORMALIZATION.md | ✓ Done |

### Security constraints maintained

- Read-only enforced at transport layer (`MetaWriteForbiddenError` for any non-GET)
- Token scope recommendation: `ads_read` only (no `ads_management`)
- `_redact_raw()` strips access_token/appsecret_proof before DB storage
- `DRY_RUN=true` and `REQUIRE_HUMAN_APPROVAL=true` unchanged
- All mock-imported data marked `is_fictitious=True`
- `META_PROVIDER=mock` default — no real API calls unless explicitly configured

---

## Phase 3: Claude Visual Analysis + Full Prompt Engine (COMPLETE)

### Deliverables

| Task | Description | Status |
|---|---|---|
| F3-01 | `CreativeHypothesis` entity — traceability from SourceAd → analysis → hypothesis → PromptVersion | ✓ Done |
| F3-02 | `CreativeAnalysis` extended — input_hash, analysis_version, observations, metric_facts, limitations, hypotheses, cost, latency | ✓ Done |
| F3-03 | `PromptTemplate.hypothesis_id` FK + `PromptVersion.content_hash, author_type, target_model` | ✓ Done |
| F3-04 | Alembic migration `c7d9e3f1a2b4` — creative_hypotheses, 13 analysis columns, 4 version columns | ✓ Done |
| F3-05 | `image_guard.py` — format check (png/jpeg/webp/gif), size limit, EXIF strip via Pillow | ✓ Done |
| F3-06 | `pricing.py` — USD/MTok table for all Claude models, `estimate_cost()` | ✓ Done |
| F3-07 | `interface.py` rewritten — Observation, MetricFact, PerformanceHypothesis sub-schemas, confidence clamping, `to_storage_dict()` | ✓ Done |
| F3-08 | `mock.py` rewritten — all Phase 3 segregated fields, video/carousel partial status | ✓ Done |
| F3-09 | `real.py` rewritten — prompt injection defense (`<untrusted_ad_data>`), tool_use, exponential backoff, JSON repair | ✓ Done |
| F3-10 | `PromptEngine` extended — 33 fields, deterministic section ordering, `content_hash()`, `new_version()` | ✓ Done |
| F3-11 | `AnalysisService` — input_hash idempotency, append-versioned analysis, AuditLog, metrics aggregation | ✓ Done |
| F3-12 | `PromptService` — generate (with optional hypothesis), revise (409 on identical hash), diff | ✓ Done |
| F3-13 | Endpoints: GET `/analyses/{id}`, GET `/prompts`, GET `/prompts/{id}`, GET `/prompts/{id}/versions`, GET `/prompt-versions/{id}`, GET `/prompt-versions/{id}/diff/{other}` | ✓ Done |
| F3-14 | Breaking change: POST `/prompts/{id}/revise` — `{id}` is now `template_id` (was `version_id`) | ✓ Done |
| F3-15 | Frontend `/ads/[id]` — full analysis panel: observations, metric facts, hypotheses, confidence bar, provider badge, limitations, policy risks | ✓ Done |
| F3-16 | Frontend `/prompts` — template list with filters (format, objective) | ✓ Done |
| F3-17 | Frontend `/prompts/[id]` — version timeline, prompt preview, structured fields, diff viewer, create revision form | ✓ Done |
| F3-18 | Nav: Prompts link added | ✓ Done |
| F3-19 | Unit tests: analysis_schema, anthropic_mock, image_guard, prompt_injection, prompt_engine_phase3, audit_no_secrets | ✓ Done |
| F3-20 | Integration tests: analysis_flow (idempotency, force, org isolation), prompt_versioning (revise, diff, 409) | ✓ Done |
| F3-21 | conftest.py: added ROOT to sys.path for `packages.*` namespace imports | ✓ Done |
| F3-22 | docs/ANTHROPIC_SETUP.md | ✓ Done |

### Test results

```
132 passed, 2 warnings
```

### Security constraints maintained

- `ANTHROPIC_PROVIDER=mock` default — no real Claude API calls unless configured
- Ad copy wrapped in `<untrusted_ad_data>` delimiters; `_sanitise()` strips injection attempts
- API keys never logged; images never logged; only tokens/latency/status recorded
- Analysis idempotency: same input → same result, no duplicate charges
- Append-versioned: old analyses never overwritten
- Immutable PromptVersion: revise always creates new row; 409 on identical content_hash
- All org isolation preserved; full AuditLog for every sensitive action

---

## Phase 4: OpenAI Image Generation + Storage + Gates + Approval (COMPLETE)

### Deliverables

| Task | Description | Status |
|---|---|---|
| F4-01 | `packages/storage` — LocalStorage (HMAC signed URLs), S3 stub, interface Protocol, path helpers | ✓ Done |
| F4-02 | `ImageBytesResult` pattern — providers return bytes; CreativeService handles persistence | ✓ Done |
| F4-03 | `MockImageClient` rewritten — real Pillow PNG, n variations, `[FICTITIOUS IMAGE]` label | ✓ Done |
| F4-04 | `RealOpenAIImageClient` — size mapping, retry/timeout, moderation_flagged, no key logging | ✓ Done |
| F4-05 | `packages/openai_image_client/pricing.py` — cost estimation table for gpt-image-2 / dall-e-3 | ✓ Done |
| F4-06 | `CreativeAsset` ORM model — original, derivative, thumbnail; role/fit_strategy/signed_url | ✓ Done |
| F4-07 | `GeneratedCreative` extended — storage_key, storage_backend, phash, variation_of_id, source_ad_id | ✓ Done |
| F4-08 | `Approval` extended — action (approve/reject/request_variation), overridden_check_ids | ✓ Done |
| F4-09 | Alembic migration `d1e2f3a4b5c6` — creative_assets table + ALTER generated_creatives, approvals | ✓ Done |
| F4-10 | `dedup.py` — sha256 exact + pHash near-duplicate (Hamming ≤ threshold) | ✓ Done |
| F4-11 | `derivative_service.py` — pad strategy (letterbox), no distortion, thumbnail 512px | ✓ Done |
| F4-12 | `QualityEngine` v4 — bytes-first API, CV checks (blur, margin), extra_findings injection | ✓ Done |
| F4-13 | `PolicyEngine` v2 — segment-aware rules, INTERNAL_ONLY_NOTICE, rule_set_version | ✓ Done |
| F4-14 | `CreativeService` — full pipeline: provider→storage→dedup→derivatives→QG→PG→status | ✓ Done |
| F4-15 | Status machine: queued→generating→generated→checking→blocked/awaiting_approval→approved/rejected | ✓ Done |
| F4-16 | `POST /creatives` — n variations, extra_formats, source_ad_id | ✓ Done |
| F4-17 | `GET /creatives`, `GET /creatives/{id}` — assets with signed_url (local), eager load | ✓ Done |
| F4-18 | `POST /creatives/{id}/quality-check` — bytes-first, stores QualityCheck record | ✓ Done |
| F4-19 | `POST /creatives/{id}/policy-check` — internal_notice field, segment-aware | ✓ Done |
| F4-20 | `POST /creatives/{id}/approve` — BLOCKED guard, owner-only override, audit log | ✓ Done |
| F4-21 | `POST /creatives/{id}/reject` — mandatory comment, audit log | ✓ Done |
| F4-22 | `POST /creatives/{id}/request-variation` — creates new record, rejects current | ✓ Done |
| F4-23 | `GET /approvals`, `GET /approvals/{id}` — queue with check summaries, signed URLs, internal_notice | ✓ Done |
| F4-24 | `GET /assets/{token}` — HMAC token validation, FileResponse, no JWT required | ✓ Done |
| F4-25 | Frontend `/approvals` — queue with thumbnails, status badges, quality/policy check results | ✓ Done |
| F4-26 | Frontend `/approvals/[id]` — detail with image preview, derivatives, findings, approve/reject/variation | ✓ Done |
| F4-27 | Unit tests: storage (18), derivatives (11), dedup (7), mock_provider (10), quality_p4 (10), policy_p4 (7) | ✓ Done |
| F4-28 | Integration tests: creative_flow_p4 (14), approval_flow (13) | ✓ Done |
| F4-29 | docs/OPENAI_SETUP.md, docs/POLICY_ENGINE.md | ✓ Done |

### Test results

```
222 passed, 1 skipped, 2 warnings
```

### Security constraints maintained

- `IMAGE_PROVIDER=mock` default — zero cost unless `OPENAI_API_KEY` is explicitly set
- API key never logged, never in DB, never in audit events
- BLOCKED creatives cannot be approved via common flow (`ALLOW_BLOCKED_OVERRIDE=false` default)
- BLOCKED override: owner-only, requires `override_blocked=true` + mandatory comment, recorded with overridden check IDs
- All approved content is immutable (Approval record with snapshot_prompt)
- New variation always creates a new record; original is rejected
- `internal_notice` always present: "does NOT guarantee Meta Ads approval"
- All private files served via HMAC-signed URLs with TTL; no direct path exposure
- Original image always preserved (separate storage key from derivatives)
- No distortion: pad strategy (letterbox) used when aspect ratios differ

---

## Phase 5: DRY_RUN Publish Simulation (COMPLETE)

### Mandatory rules enforced

- `DRY_RUN=true` by default — no real Meta write methods reachable
- All simulated ads start as `PAUSED` (frozen Pydantic field + `@field_validator` enforces regardless of input)
- Creatives without approval cannot proceed
- Creatives with BLOCKED checks cannot proceed
- All simulations have an idempotency key (`(org_id, idempotency_key)` unique constraint)
- Payloads are sanitized before log (strips `access_token`, `appsecret_proof`, `key`, `token`, `password`, `secret`)
- Simulated IDs always prefixed `simulated_*` — never invented real Meta IDs
- Real Meta publish endpoint returns 501 Not Implemented until Phase 6

### Deliverables

| Task | Description | Status |
|---|---|---|
| F5-01 | `PublicationDraft` + `PublicationAttempt` ORM models with `(org_id, idempotency_key)` unique constraint, `payload_hash` | ✓ Done |
| F5-02 | `AuditLog` extended — `idempotency_key`, `correlation_id`, `approval_id`, `limits_checked` (nullable, backward-compatible) | ✓ Done |
| F5-03 | Alembic migration `e5f6a7b8c9d0` — publication_drafts, publication_attempts, audit_logs ALTER | ✓ Done |
| F5-04 | `packages/meta_client/interface.py` refactored — `MetaReadClient`, `MetaWriteClient`, `MetaPublisher` protocols; `MetaClientProtocol` alias preserved | ✓ Done |
| F5-05 | `packages/meta_client/publish/placeholders.py` — named PENDING_* constants, `is_placeholder()`, `resolve()` | ✓ Done |
| F5-06 | `packages/meta_client/publish/dtos.py` — `CampaignPayload`, `AdSetPayload`, `AdPayload` with frozen PAUSED status (validator forces PAUSED regardless of input), `MetaPublishPayload`, `SimulatedPublishResponse` | ✓ Done |
| F5-07 | `packages/meta_client/publish/dry_run_publisher.py` — `DryRunPublisher`: no HTTP import, cannot make network calls, generates `simulated_*` IDs | ✓ Done |
| F5-08 | `packages/meta_client/publish/write_client_real.py` — `RealMetaWriteClient`: all 7 methods raise `MetaPublishDisabledError` (Phase 6 stub) | ✓ Done |
| F5-09 | `packages/meta_client/publish/factory.py` — `get_meta_publisher(dry_run=True)`: asserts dry_run, returns `DryRunPublisher`; `AssertionError` on `dry_run=False` | ✓ Done |
| F5-10 | `app/services/publication_guards.py` — 13 pure guard functions: dry_run, org scope, approval, BLOCKED check, creative status, RBAC, budget present, daily spend limit, experiment budget, daily ads count, landing URL (SSRF), page reference, idempotency | ✓ Done |
| F5-11 | `app/services/publication_service.py` — `PublicationService`: `build_payload()`, `validate()`, `dry_run()` with idempotency safe-retry, canonical payload hash, sanitize | ✓ Done |
| F5-12 | `app/schemas/publish.py` — `DryRunRequest`, `ValidateRequest`, `DraftUpsertRequest`, `DryRunResponse`, `ValidateResponse`, `DraftOut`, `AttemptOut` | ✓ Done |
| F5-13 | `app/routers/publish.py` rewritten — `POST /publish/meta/validate`, `POST /publish/meta/dry-run`, `POST /publish/meta` (501), `POST /publish/meta/drafts`, `GET /publish/meta/drafts`, `GET /publication-drafts/{id}`, `GET /publication-attempts/{id}` | ✓ Done |
| F5-14 | `app/config.py` — `publication_idempotency_ttl_hours: int = 24`, `max_daily_spend`, `max_daily_new_ads` fields | ✓ Done |
| F5-15 | Frontend `apps/web/app/publish/page.tsx` — DRY_RUN banner, creative selector, campaign/adset/ad forms, budget input, idempotency key management, validate + simulate buttons, check results, payload JSON viewer, simulated IDs panel with FICTÍCIOS badge, simulation history table | ✓ Done |
| F5-16 | Nav updated — "Publicação (DRY_RUN)" link | ✓ Done |
| F5-17 | `apps/web/lib/api.ts` — `GuardCheckResult`, `SimulatedPublishResponse`, `ValidateResponse`, `DryRunResponse`, `PublicationAttemptOut`, `api.publish.validate()`, `api.publish.dryRun()`, `api.publish.getAttempt()`, `api.publish.listDrafts()` | ✓ Done |
| F5-18 | Unit tests: `test_publish_dtos.py` (frozen PAUSED, objectives, placeholders, serialization) | ✓ Done |
| F5-19 | Unit tests: `test_publication_guards.py` (all 13 guards, run_all_guards, SSRF, idempotency) | ✓ Done |
| F5-20 | Unit tests: `test_dry_run_publisher.py` — **critical security test**: patching `httpx.AsyncClient` to raise `AssertionError` if instantiated during DRY_RUN | ✓ Done |
| F5-21 | Integration tests: `test_publication_flow.py` (13 tests: approval guard, BLOCKED guard, viewer forbidden, budget exceeded, success saves attempt+audit, idempotent retry, conflict, org isolation, validate no-persist, SSRF, PAUSED status, no-write security, GET attempt, audit no-secrets) | ✓ Done |
| F5-22 | Integration tests: `test_dry_run.py` (3 tests: requires approval, idempotency, saves payload no write) | ✓ Done |
| F5-23 | Docs: README, IMPLEMENTATION_PLAN, ARCHITECTURE, SECURITY, META_SETUP updated | ✓ Done |

### Test results

```
298 passed, 7 skipped, 13 warnings
```

### Security constraints maintained

- `DryRunPublisher` has zero HTTP imports — physically cannot make network calls
- `RealMetaWriteClient` requires `access_token` and `app_secret` — raises `TypeError` without credentials
- `get_meta_publisher(dry_run=False)` raises `ValueError` — no accidental real publisher without `write_enabled=True`
- Payload hash `sha256(json.dumps(payload, sort_keys=True))` used for idempotency comparison
- Sensitive field names (`access_token`, `appsecret_proof`, `key`, `token`, `password`, `secret`) redacted with `***REDACTED***` in all stored payloads
- SSRF guard blocks 10.x, 172.16.x, 192.168.x, 127.x, 169.254.x, and AWS/GCP/Azure metadata hostnames
- Simulated IDs use `simulated_{type}_{uuid4().hex[:12]}` format — cannot be confused with real Meta IDs
- Correlation ID from `X-Correlation-ID` header or auto-generated UUID per request
- Two AuditLog records per dry-run: intent (before simulation) and result (after)

---

## Phase 6: Real Meta Publish (COMPLETE)

### Mandatory rules enforced

- Two-flag safety interlock: BOTH `DRY_RUN=false` AND `META_WRITE_ENABLED=true` required for any real write
- All real ads created as `PAUSED` — never `ACTIVE`; enforced at DTO validator + client guard + Meta response validation
- Activation is a separate manual action requiring `owner` role + `confirmation` = `meta_ad_id`
- Emergency pause has minimal barriers — any authenticated user; no confirmation required
- `publish_real_task` has `max_retries=0` — never activates in retry
- Tokens never logged (`access_token`, `app_secret` redacted in all audit/log paths)
- Non-idempotent operations never repeated without reconciliation (`find_by_idempotency_tag`)
- All real operations generate AuditLog records (intent + result)
- If Meta returns non-PAUSED after create → `requires_manual_review=True`, safe pause attempted
- Automated tests never publish real ads (real tests are optional and gated behind flags)
- No IDs or permissions are invented; all are derived from Meta API responses

### Deliverables

| Task | Description | Status |
|---|---|---|
| F6-01 | `WriteGraphTransport` — POST/multipart HTTP, HMAC appsecret_proof, token redaction, request_id capture, `idempotent` flag: non-idempotent failures after send → `MetaWriteAmbiguousError` | ✓ Done |
| F6-02 | `RealMetaWriteClient` — 7 real methods, PAUSED guard before POST, reconciliation via `find_by_idempotency_tag()` (returns first match or None), `upload_image` multipart | ✓ Done |
| F6-03 | Idempotency tag: short UUID suffix embedded in resource names `"Campaign [abc123]"` for reconciliation | ✓ Done |
| F6-04 | `RealPublisher` — 5-step pipeline: image upload → create campaign → create adset → create ad creative → create ad; resume skips already-completed steps | ✓ Done |
| F6-05 | Meta response validation: `effective_status != PAUSED` after create → `requires_manual_review=True` + safe pause attempt | ✓ Done |
| F6-06 | `PublishedAd` ORM model — `meta_campaign_id`, `meta_adset_id`, `meta_ad_id`, `idempotency_tag`, `requires_manual_review`, `workflow_state` | ✓ Done |
| F6-07 | `PublicationStep` ORM model — one row per pipeline step; `state`, `meta_node_id`, `meta_request_id`, `is_recoverable`, `error_detail` | ✓ Done |
| F6-08 | `AuditLog.emergency` boolean field — default False; True only for emergency pause | ✓ Done |
| F6-09 | Alembic migration `f1a2b3c4d5e6` — published_ads table + publication_steps table + audit_logs ALTER | ✓ Done |
| F6-10 | `publication_guards.py` extended — 3 new real-mode guards: `guard_real_mode_enabled`, `guard_write_enabled`, `guard_credentials_valid`; promoted guards: `min_config` (warning→blocked), `landing_url` (warning→blocked); `_REAL_GUARD_SEQUENCE` (16 guards) | ✓ Done |
| F6-11 | `PublicationService.publish_real()` — runs guards, writes intent AuditLog, persists `PublishedAd` + `PublicationAttempt`, calls `RealPublisher`, persists steps, updates records, writes result AuditLog | ✓ Done |
| F6-12 | `PublicationService.refresh_status()` — queries Meta GET `effective_status`; updates `PublishedAd.status` | ✓ Done |
| F6-13 | `PublicationService.activate()` — owner role check, confirmation = meta_ad_id, budget re-validation, one attempt (max_retries=1 for non-idempotent); writes AuditLog | ✓ Done |
| F6-14 | `PublicationService.pause()` — regular and emergency; emergency skips role check; `AuditLog.emergency=True` for emergency | ✓ Done |
| F6-15 | `publish_real_task` Celery task — max_retries=0, acks_late=True, reject_on_worker_lost=True; all payload fields as individual params; `object.__setattr__` for `_raw_bytes` injection; `_mark_attempt_failed()` on unhandled errors | ✓ Done |
| F6-16 | `app/schemas/publish.py` — `RealPublishRequest`, `StepOut`, `RealPublishResponse`, `PublishStatusResponse`, `ActivateRequest`, `ActivateResponse`, `PauseResponse`, `PublishedAdOut` | ✓ Done |
| F6-17 | Router endpoints: `POST /publish/meta` (real), `GET /publication-attempts/{id}/status`, `GET /published-ads`, `GET /published-ads/{id}`, `POST /published-ads/{id}/refresh-status`, `POST /published-ads/{id}/activate` (owner), `POST /published-ads/{id}/pause` (editor), `POST /published-ads/{id}/emergency-pause` (any auth user) | ✓ Done |
| F6-18 | Frontend `apps/web/app/published-ads/page.tsx` — list with mode filter, refresh/activate/pause/emergency-pause per row, status badges, manual review flag | ✓ Done |
| F6-19 | `apps/web/lib/api.ts` — Phase 6 types (`StepOut`, `RealPublishResponse`, `PublishStatusResponse`, `PublishedAdOut`, `ActivateResponse`, `PauseResponse`) + `api.publish.real()`, `api.publish.getAttemptStatus()`, `api.publishedAds.*` | ✓ Done |
| F6-20 | Nav updated — "Anúncios Publicados" link | ✓ Done |
| F6-21 | Unit tests: `test_write_transport.py` (9 tests: HMAC, redact, GET, POST, rate limit, permission, policy) | ✓ Done |
| F6-22 | Unit tests: `test_real_write_client.py` (9 tests: PAUSED enforcement, get_status, update, find tag, upload) | ✓ Done |
| F6-23 | Unit tests: `test_publish_gate_real.py` (9 tests: guard counts, interlock flags, min_config, landing_url) | ✓ Done |
| F6-24 | Unit tests: `test_reconciliation.py` (4 tests: resume skips uploaded, happy path, non-PAUSED triggers review, campaign reuse) | ✓ Done |
| F6-25 | Integration tests: `test_publish_real_flow.py` (5 tests: DRY_RUN block, confirm_paused check, attempt status, org isolation, emergency pause auth) | ✓ Done |
| F6-26 | Integration tests: `test_activation_flow.py` (4 tests: activate blocked DRY_RUN, pause blocked DRY_RUN, endpoint guards, 404) | ✓ Done |
| F6-27 | Integration tests: `test_emergency_pause.py` (4 tests: endpoint exists, 404, AuditLog.emergency default, AuditLog.emergency=True) | ✓ Done |
| F6-28 | Docs: README, IMPLEMENTATION_PLAN, ARCHITECTURE, SECURITY, META_SETUP, DEPLOYMENT updated | ✓ Done |

### Test results

```
343 passed, 7 skipped, 13 warnings
```

### Security constraints maintained

- Two-flag interlock: `DRY_RUN=false` AND `META_WRITE_ENABLED=true` both required for real writes
- No ad ever created as ACTIVE — DTO validator (`@field_validator`) + client guard (`assert payload["status"] == "PAUSED"`) + Meta response check
- Activation requires `owner` role + `confirmation == meta_ad_id` — two independent checks
- Emergency pause: no role required, no confirmation required, minimal barriers, audit `emergency=True`
- `max_retries=0` on Celery task — the task that creates real ads never retries automatically
- `access_token` and `app_secret` never logged, never in audit payload, never in DB
- Non-idempotent creates: reconciliation via `find_by_idempotency_tag()` before every create
- `MetaWriteAmbiguousError` raised when non-idempotent POST fails after send — caller must reconcile
- `WriteGraphTransport` creates new `httpx.AsyncClient` per request — no persistent session that could leak tokens
- Budget never increased automatically; all budget changes require explicit human input

---

## Phase 7: Experiments + Evaluations + Learning Lifecycle + Next Round (COMPLETE)

### Mandatory rules enforced

- **No automatic fine-tuning** — the loop never trains or tunes a model; it only suggests human-reviewed next rounds
- **No automatic image generation** — `NextRoundService` records `auto_image_generation: False`; suggestions require human approval before any creative is generated
- **No automatic budget changes** — `DecisionService` never writes budget; `suggested_action` is advisory only, `executed_action` requires a human actor
- **Never declare a winner without sufficient data** — the evaluator gates `winner_candidate` behind all minimum criteria (impressions, spend, clicks, days, difference, confidence) AND maturation
- **New learnings always start `provisional`** — never created as `confirmed`
- **Learning confirmation requires human review** — `provisional → confirmed` needs a reviewer; `provisional → rejected` requires a mandatory comment
- **EXPLORATORY never attributes causality** — `causal_attribution=False` always; max reachable state is `promising` (never `winner_candidate`)
- **CONTROLLED enforces single-variable isolation** — each test variant changes exactly one variable == `primary_variable`
- **Workers are idempotent** — metric collection uses a unique constraint; re-runs upsert, never duplicate
- **Timezone `America/Sao_Paulo`** for all Beat schedules and report windows
- **AuditLog** recorded for every sensitive action (create, start, stop, complete, decision, learning confirm/reject, suggestion approve/reject)
- All prior protections preserved (DRY_RUN, REQUIRE_HUMAN_APPROVAL, idempotency, budget limits, org isolation)

### Deliverables

| Task | Description | Status |
|---|---|---|
| F7-01 | `packages/analytics_engine/stats.py` — Beta-Binomial posterior via `math.lgamma` + Lentz continued-fraction (no scipy); confidence, credible interval, prob-variant-beats-control | ✓ Done |
| F7-02 | `packages/analytics_engine/aggregator.py` — winsorization for outlier-robust ROAS, `safe_sum` null semantics, per-variant `AggregatedMetrics` | ✓ Done |
| F7-03 | `packages/experiment_engine/guards.py` — 7 guards: baseline, controlled single-variable, variant hypothesis, comparable budget/audience/window, experiment budget cap | ✓ Done |
| F7-04 | `packages/experiment_engine/evaluator.py` — conservative state machine (insufficient_data→collecting→inconclusive→promising→underperforming→winner_candidate→completed→stopped_for_safety), EXPLORATORY caps, peeking-risk limitation always present | ✓ Done |
| F7-05 | `packages/experiment_engine/diversity_scorer.py` — 4 penalties (near-identical prompts, visual repetition, deep variation chains, excessive learning reuse), 128-d SHA256 mock embeddings | ✓ Done |
| F7-06 | Models: `Experiment`/`ExperimentVariant` extended (16 + 5 cols), `VariantPerformanceSnapshot`, `ExperimentEvaluation` (append-only), `OptimizationDecision`, `Learning`, `LearningUsage`, `ExperimentSuggestion` | ✓ Done |
| F7-07 | Alembic migration `a1b2c3d4e5f6` — ALTER experiments + variants, CREATE 6 tables; `batch_alter_table` for SQLite; circular FK `baseline_variant_id` via `use_alter=True` | ✓ Done |
| F7-08 | `ExperimentService` — CRUD + lifecycle (draft→running→stopped/completed); re-queries with `selectinload(variants)` after commit; guards on create + start | ✓ Done |
| F7-09 | `EvaluationService` — append-only `evaluate()`; never overwrites; idempotent metric collection via `uq_variant_snapshot_key` | ✓ Done |
| F7-10 | `DecisionService` — `VALID_ACTIONS` advisory set; budget never changed (`max_automatic_budget_increase_percent=0`); `executed_action` requires human actor | ✓ Done |
| F7-11 | `LearningService` — create starts `provisional`; `confirm()` requires reviewer; `reject()` requires mandatory comment; mock-embedding on create | ✓ Done |
| F7-12 | `NextRoundService` — diversity-scored suggestions; records `auto_image_generation: False`; status `pending_approval`; no auto publish | ✓ Done |
| F7-13 | `RetrievalService` — 128-d mock embeddings, cosine similarity over JSONB (no pgvector in tests) | ✓ Done |
| F7-14 | Schemas: `experiment.py`, `learning.py`, `suggestion.py`, `report.py`, `common.py` (PaginatedResponse) | ✓ Done |
| F7-15 | `routers/experiments.py` — full lifecycle, evaluate, metrics, decisions, suggest-next-round; `suggestions_router` CRUD | ✓ Done |
| F7-16 | `routers/learnings.py` — create, list, get, confirm, reject | ✓ Done |
| F7-17 | `routers/reports.py` — GET /reports/daily, /reports/weekly | ✓ Done |
| F7-18 | `worker/tasks/experiment_tasks.py` — collect_variant_metrics, dispatch, compute_evaluations, anomaly detectors (spend, zero-conversions, rejected ads), update/flag status, daily/weekly report, suggest_next_round; all `max_retries=0`, `acks_late=True`, idempotent | ✓ Done |
| F7-19 | `worker/celery_app.py` — Beat schedule with `timezone=America/Sao_Paulo`, crontab for daily/weekly reports | ✓ Done |
| F7-20 | Frontend `/experiments` (list + filters), `/experiments/[id]` (lifecycle, evaluation, metrics, decisions, suggestions), `/experiments/new` (EXPLORATORY/CONTROLLED selector) | ✓ Done |
| F7-21 | Frontend `/learnings` (confirm/reject), `/suggestions` (approve/reject), `/reports` (daily/weekly tabs) | ✓ Done |
| F7-22 | Nav + `apps/web/lib/api.ts` — Phase 7 types and `api.experiments.*`, `api.learnings.*`, `api.suggestions.*`, `api.reports.*` | ✓ Done |
| F7-23 | Unit tests: `test_stats.py` (22 — beta-binomial, confidence, edge cases) | ✓ Done |
| F7-24 | Unit tests: `test_experiment_guards.py` (12 — baseline, single-variable, hypothesis, run-all) | ✓ Done |
| F7-25 | Unit tests: `test_evaluator.py` (9 — insufficient data, EXPLORATORY caps, CONTROLLED winner, peeking limitation) | ✓ Done |
| F7-26 | Unit tests: `test_diversity_scorer.py` (9 — penalties, embeddings) | ✓ Done |
| F7-27 | Unit tests: `test_aggregator.py` (9 — winsorize, safe_sum, per-variant) | ✓ Done |
| F7-28 | Integration tests: `test_experiment_flow.py` (18 — CRUD, org isolation, lifecycle, append-only evaluation, decision-does-not-change-budget, learning lifecycle) | ✓ Done |
| F7-29 | Seed extended — running CONTROLLED experiment + 2 variants + 2 matured snapshots + 1 evaluation (promising) + 1 decision (continue) + 2 learnings (1 confirmed, 1 provisional) + 1 suggestion (pending_approval) | ✓ Done |
| F7-30 | Docs: `docs/EXPERIMENTATION.md`; README, ARCHITECTURE, SECURITY, IMPLEMENTATION_PLAN updated | ✓ Done |

### Test results

```
422 passed, 7 skipped, 13 warnings
```

(79 Phase 7 tests added on top of the 343 from Phase 6.)

### Security constraints maintained

- No model fine-tuning or training anywhere in the loop — suggestions only
- `NextRoundService` records `auto_image_generation: False`; no creative generated without human approval
- `DecisionService` never mutates budget; advisory `suggested_action` only
- `winner_candidate` unreachable until all minimum criteria + maturation are satisfied
- EXPLORATORY: `causal_attribution=False` always; state capped at `promising`
- CONTROLLED: single-variable isolation enforced by guard before start
- Learnings start `provisional`; confirmation needs human review; rejection needs a comment
- Metric collection idempotent via `uq_variant_snapshot_key` (variant, dates, level, breakdown, attribution window)
- All Beat schedules and report windows use `America/Sao_Paulo`
- Full AuditLog for create/start/stop/complete/decision/learning/suggestion actions
- Org isolation, DRY_RUN, REQUIRE_HUMAN_APPROVAL, idempotency, and budget limits all preserved
