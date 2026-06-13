# Architecture — Creative Loop

## Component overview

```
┌────────────┐     HTTP/JSON      ┌──────────────────────────────┐
│  Next.js   │ ◀────────────────▶ │  FastAPI (apps/api)          │
│ (apps/web) │  JWT httpOnly cookie│  REST + OpenAPI              │
└────────────┘                    └───────┬──────────────┬───────┘
                                          │              │
                              SQLAlchemy 2│async    Celery tasks
                                          │              │
                                  ┌───────▼──────┐  ┌────▼─────────┐
                                  │ PostgreSQL   │  │   Redis      │
                                  │ + pgvector   │  │ (broker)     │
                                  └──────────────┘  └────┬─────────┘
                                                         │
                                                ┌────────▼─────────┐
                                                │ Celery worker +  │
                                                │ Celery Beat      │
                                                │ (apps/worker)    │
                                                └──────────────────┘
                          ┌─────────────────────────────────────────────┐
                          │              packages/                       │
                          │  anthropic_client  openai_image_client       │
                          │  meta_client       policy_engine             │
                          │  quality_engine    prompt_engine             │
                          │  storage           analytics_engine          │
                          │  experiment_engine                           │
                          └─────────────────────────────────────────────┘
```

## Key patterns

### Multi-tenancy
Every business table has `organization_id`. The `get_current_org` FastAPI dependency extracts the org from the JWT and injects it into every query. Org B can never see Org A's data.

### Provider abstraction
Each external API has a `Protocol` interface and two implementations: `mock` (deterministic, no cost) and `real` (SDK-backed). Selected via env vars:
- `ANTHROPIC_PROVIDER=mock|real`
- `IMAGE_PROVIDER=mock|openai`
- `META_PROVIDER=mock`

### Prompt versioning
`PromptVersion` records are immutable. `revise` creates a new version with incremented `version_number`, a unified diff in `diff_summary`, and preserves the parent via `parent_version_id`. The original is never overwritten.

### Safety gates (in order)
1. `DRY_RUN` — publish endpoint blocked if false (Phase 1)
2. `REQUIRE_HUMAN_APPROVAL` — `Approval` record required before any publish
3. `QualityCheck` + `PolicyCheck` — BLOCKED result prevents approval
4. Budget limits — `daily_budget > MAX_DAILY_SPEND` → 422
5. Idempotency key — duplicate publish rejected with 409

### Audit trail
`AuditLog` records are written before every sensitive action (analyze, generate_prompt, generate_creative, approve, publish). Each row includes `actor_id`, `action`, `entity_type`, `entity_id`, `payload`, `result`, `dry_run`.

### Database portability
`UUIDType` and `JSONBType` are custom `TypeDecorator`s that use PostgreSQL-native types (`UUID`, `JSONB`) on PostgreSQL and `VARCHAR(36)` / `JSON` on SQLite. All tests run against SQLite in-memory.

## Phase 7 additions

### Experiment modes

Two modes with different epistemics:

- **EXPLORATORY** — many variables may change per variant. `causal_attribution` is **always False**. The evaluator never returns `winner_candidate`; the best reachable state is `promising`. Used for broad idea discovery.
- **CONTROLLED** — single-variable isolation. `guard_controlled_single_variable` blocks start unless each test variant changes exactly one variable equal to `primary_variable`. Only this mode can reach `winner_candidate`, and only with `causal_attribution=True`.

### Conservative evaluator (`packages/experiment_engine/evaluator.py`)

State machine, monotonically cautious:

```
insufficient_data → collecting → inconclusive → promising
                                              → underperforming
                                              → winner_candidate (CONTROLLED only)
                                              → completed | stopped_for_safety
```

`winner_candidate` is gated behind **all** of: `min_impressions`, `min_spend`, `min_clicks`, `min_days`, `min_difference`, `min_confidence`, **and** snapshot maturation (`maturation_window_days`). A `peeking_risk` limitation is always attached when evaluating mid-window. Confidence comes from a Beta-Binomial posterior computed in `packages/analytics_engine/stats.py` using `math.lgamma` + a Lentz continued-fraction — **no scipy dependency**.

### Outlier-robust aggregation (`packages/analytics_engine/aggregator.py`)

Per-variant metrics are aggregated with **winsorization** (clamp extremes to configured percentiles) so a single runaway ROAS day cannot dominate. `safe_sum` returns `None` (not `0.0`) when every input is null, preserving the "no data" vs "zero" distinction.

### Append-only evaluation

Each `evaluate()` call inserts a new `ExperimentEvaluation` row — **never** an update. The history of how the experiment was judged over time is fully preserved (and auditable for peeking).

### Decisions never touch budget

`OptimizationDecision` carries an advisory `suggested_action` (`continue | pause | review | create_new_hypothesis | wait_more_data`). `executed_action` is filled **only** when a human explicitly acts. `DecisionService` never increases or decreases budget — `max_automatic_budget_increase_percent=0`.

### Learning lifecycle

```
(created) → provisional ──human review──▶ confirmed
                        └──comment req.──▶ rejected
```

No learning is born `confirmed`. Confirmation requires a human reviewer; rejection requires a mandatory `review_comment` (counter-evidence). `supersedes_id` links a newer learning that overrides an older one. Each `Learning` carries a 128-d embedding (SHA256 mock in dev/tests, pgvector in production) stored as JSONB for SQLite portability.

### Diversity scoring & next round (`NextRoundService` + `diversity_scorer.py`)

When suggesting the next round, the scorer penalizes four redundancy types: near-identical prompts, visual repetition (pHash), deep variation chains, and excessive reuse of the same learning. The resulting `ExperimentSuggestion`:
- records `auto_image_generation: False` — **no creative is generated automatically**
- starts as `pending_approval` — **never auto-approved, never auto-published**
- requires explicit human approval before any downstream generation

### Idempotent workers + Beat (`America/Sao_Paulo`)

`collect_variant_metrics` upserts `VariantPerformanceSnapshot` keyed by `uq_variant_snapshot_key` (variant_id, date_start, date_stop, level, breakdown_key, attribution_window) — re-running a window never duplicates rows. All Phase 7 tasks set `max_retries=0` and `acks_late=True`. Anomaly detectors (anomalous spend, zero conversions, rejected ads) flag for human review but never auto-pause budget. Daily/weekly report crontabs run in `America/Sao_Paulo`.

### MissingGreenlet avoidance

Lifecycle methods (`create`, `start`, `stop`, `complete`) re-query with `selectinload(Experiment.variants)` after commit instead of `db.refresh()`, so the `variants` relationship is eagerly loaded before FastAPI serializes `ExperimentOut` — avoiding `MissingGreenlet` from lazy-loading outside an async greenlet.

### New entities (Phase 7)

- `VariantPerformanceSnapshot` — per-variant metric snapshot (mirrors `PerformanceSnapshot`); `is_matured` flips once `maturation_window_days` passes
- `ExperimentEvaluation` — append-only judgement record; `per_variant_result`, `confidence`, `limitations`, `causal_attribution`
- `OptimizationDecision` — advisory; `suggested_action` vs human-only `executed_action`
- `Learning` / `LearningUsage` — provisional→confirmed/rejected lifecycle + usage tracking
- `ExperimentSuggestion` — diversity-scored next-round proposal; `pending_approval`
- `Experiment` / `ExperimentVariant` extended with mode, criteria JSON, window, budget, `baseline_variant_id`

### API surface additions (Phase 7)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST/GET | `/experiments` | editor+/auth | Create / list experiments (mode + status filters) |
| GET | `/experiments/{id}` | authenticated | Experiment detail + variants |
| POST | `/experiments/{id}/start` | editor+ | Run guards, transition draft→running |
| POST | `/experiments/{id}/stop` | editor+ | Stop with reason |
| POST | `/experiments/{id}/complete` | owner | Complete with stop reason |
| POST | `/experiments/{id}/evaluate` | editor+ | Append-only evaluation |
| GET | `/experiments/{id}/metrics` | authenticated | Variant snapshots |
| POST/GET | `/experiments/{id}/decisions` | editor+/auth | Create / list advisory decisions |
| POST | `/experiments/{id}/suggest-next-round` | editor+ | Generate diversity-scored suggestion |
| GET/POST | `/suggestions` | auth/editor+ | List / manage suggestions |
| POST | `/suggestions/{id}/approve` · `/reject` | admin+ | Human approval gate |
| POST/GET | `/learnings` | editor+/auth | Create (provisional) / list |
| POST | `/learnings/{id}/confirm` | admin+ | Human review → confirmed |
| POST | `/learnings/{id}/reject` | admin+ | Reject with mandatory comment |
| GET | `/reports/daily` · `/reports/weekly` | authenticated | Aggregated reports (SP timezone) |

## Phase 6 additions

### Two-flag safety interlock

Real Meta writes require BOTH flags set explicitly:
```
DRY_RUN=false           — must opt out of simulation mode
META_WRITE_ENABLED=true — must opt into real write mode
```
Either flag alone is not enough. `guard_real_mode_enabled` and `guard_write_enabled` are the first two guards in `_REAL_GUARD_SEQUENCE`.

### Real publish pipeline

```
RealPublishRequest (creative_id + idempotency_key + confirm_paused + landing_url + …)
  → 16 real-mode guards (includes 3 new: real_mode, write_enabled, credentials_valid;
                          2 promoted: min_config → blocked, landing_url → blocked)
  → intent AuditLog written
  → PublishedAd(dry_run=False, status="PAUSED") + PublicationAttempt persisted
  → Celery publish_real_task dispatched (max_retries=0, acks_late=True)
      → RealPublisher.publish():
          1. find_by_idempotency_tag("campaigns") → skip if exists
          2. upload_image → PublicationStep(state="image_uploaded")
          3. create_campaign (PAUSED) → assert effective_status == PAUSED
          4. create_adset (PAUSED)
          5. create_ad (PAUSED) → validate effective_status
      → PublicationStep rows persisted per step
      → PublishedAd updated (meta_*_id fields, workflow_state=completed)
  → result AuditLog written
```

### WriteGraphTransport

Separate from `MetaGraphTransport` (read-only). Handles:
- `POST` (form data) and multipart (image upload)
- HMAC appsecret_proof on every request
- `idempotent` flag: idempotent ops retry and surface original error; non-idempotent ops after send → `MetaWriteAmbiguousError`
- `request_id` captured from `x-fb-request-id` response header
- Creates new `httpx.AsyncClient` per request — no persistent token storage

### Reconciliation pattern

Every non-idempotent create:
1. `find_by_idempotency_tag(account_id, resource, tag)` — searches existing resources by name substring
2. First match returned or `None`
3. On match → skip create, reuse existing ID
4. On `None` → proceed with POST

Idempotency tag format: `[{8-char uuid suffix}]` embedded in the resource name. The same tag is stored in `PublishedAd.idempotency_tag`.

### Manual activation flow

```
POST /published-ads/{id}/activate
  → require_roles("owner")
  → guard DRY_RUN=false
  → guard META_WRITE_ENABLED=true
  → validate confirmation == ad.meta_ad_id
  → re-validate budget limits
  → intent AuditLog written
  → update_ad_status(meta_ad_id, "ACTIVE") — one call, no retry
  → PublishedAd.status = "ACTIVE"
  → result AuditLog written
```

### Emergency pause flow

```
POST /published-ads/{id}/emergency-pause
  → get_current_user (any authenticated user — no role check)
  → guard DRY_RUN=false
  → guard META_WRITE_ENABLED=true
  → intent AuditLog(emergency=True) written
  → update_ad_status(meta_ad_id, "PAUSED")
  → PublishedAd.status = "PAUSED"
  → result AuditLog(emergency=True) written
```

### New entities (Phase 6)

- `PublishedAd` — one row per published ad; tracks `meta_campaign_id`, `meta_adset_id`, `meta_ad_id`, `idempotency_tag`, `requires_manual_review`, `workflow_state`, `dry_run` (False = real)
- `PublicationStep` — one row per pipeline step; `state` ∈ {image_uploaded, campaign_created, adset_created, ad_created}, `meta_node_id`, `meta_request_id`, `is_recoverable`

### API surface additions (Phase 6)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/publish/meta` | editor+ | Real publish (DRY_RUN=false required) |
| GET | `/publication-attempts/{id}/status` | authenticated | Attempt + steps detail |
| GET | `/published-ads` | authenticated | List with mode/status/creative filters |
| GET | `/published-ads/{id}` | authenticated | Single published ad detail |
| POST | `/published-ads/{id}/refresh-status` | editor+ | Query Meta for effective_status |
| POST | `/published-ads/{id}/activate` | owner only | Manual activation (PAUSED → ACTIVE) |
| POST | `/published-ads/{id}/pause` | editor+ | Regular pause (ACTIVE → PAUSED) |
| POST | `/published-ads/{id}/emergency-pause` | any auth user | Emergency pause, minimal barriers |

## Phase 5 additions

### DRY_RUN publish pipeline

```
DryRunRequest (creative_id + idempotency_key + budget + …)
  → 13 publication guards (pure functions, no side effects)
      dry_run_enabled | org_scope | approval_present | not_blocked
      creative_status | rbac | budget_present | daily_spend_limit
      experiment_budget | daily_ads_count | landing_url (SSRF) | page_reference | idempotency
  → idempotency check: safe-retry (same hash) | conflict (different hash)
  → intent AuditLog written
  → DryRunPublisher.publish() → SimulatedPublishResponse (simulated_* IDs, zero HTTP)
  → PublishedAd(dry_run=True) persisted
  → PublicationAttempt persisted
  → result AuditLog written
  → DryRunResponse returned (201)
```

### Protocol split (`packages/meta_client/interface.py`)
- `MetaReadClient` — read-only Meta API methods (iter_campaigns, iter_insights, …)
- `MetaWriteClient` — write methods stub (Phase 6)
- `MetaPublisher` — publish protocol (build_payload → publish → SimulatedPublishResponse)
- `MetaClientProtocol = MetaReadClient` — backward-compatible alias

### DryRunPublisher safety
- File has **zero HTTP imports** — cannot make network calls even if mistakenly wired
- `RealMetaWriteClient` raises `MetaPublishDisabledError` on all 7 methods
- `get_meta_publisher(dry_run=False)` raises `AssertionError` — factory blocks any real publisher path
- Critical test: `test_no_http_write_calls_during_dry_run` patches `httpx.AsyncClient.__init__` to raise — verifies zero HTTP during DRY_RUN

### Idempotency design
- `PublicationAttempt` has `UniqueConstraint("organization_id", "idempotency_key")`
- `payload_hash = sha256(json.dumps(payload_dict, sort_keys=True))` — canonical across key order
- Same key + same hash → safe-retry → returns existing result (200 OK)
- Same key + different hash → conflict → 409
- New key → proceeds → 201 Created

### Payload sanitization
`_sanitize_payload(dict)` recurses through all nested dicts and redacts any key whose name contains: `access_token`, `appsecret_proof`, `secret`, `token`, `key`, `password`. Stored payloads in `PublicationAttempt.checks` and `AuditLog.payload` are always sanitized.

### SSRF protection (landing URL guard)
Resolves hostname → rejects if IP matches: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.0.0/16`. Also rejects hostname substrings: `169.254.169.254`, `metadata.google.internal`, `metadata.azure.internal`.

### New entities (Phase 5)
- `PublicationDraft` — draft publication config per creative (campaign/adset/ad JSON blobs)
- `PublicationAttempt` — each simulated publish attempt; unique on `(org_id, idempotency_key)`

## Phase 4 additions

### Storage abstraction (`packages/storage`)
`StorageBackend` Protocol with two implementations:
- **LocalStorage** — files at `<base_dir>/<org_id>/<uuid>.ext`. Signed URLs are HMAC-authenticated tokens (`/assets/{token}`) with configurable TTL. No direct path exposure.
- **S3Stub** — raises `NotImplementedError`. Wire up with `aioboto3` for production.

### Creative generation pipeline (`CreativeService`)
```
PromptVersion
  → ImageProvider.generate() → ImageBytesResult (bytes in memory)
  → sha256 + pHash
  → find_duplicate_hash() / find_similar_phash()
  → storage.put() → StoredObject
  → make_derivative() for each extra_format (pad strategy, no distortion)
  → make_thumbnail()
  → QualityEngine.check(data=bytes, extra_findings=dedup_findings)
  → PolicyEngine.check(text=prompt_text)
  → status: blocked | awaiting_approval
```

### Quality Gate multi-stage
- **Stage 1 — deterministic**: format, file size, dimensions, prompt present, file corrupt.
- **Stage 2 — CV** (Pillow + numpy): blur detection (Laplacian gradient variance), margin safe area (edge variance), brand color presence. Configurable via `QUALITY_CV_ENABLED`.
- **Stage 3 — AI**: stub only. Enable via `QUALITY_AI_ENABLED=true` in a future phase.

Deduplication findings (hash_duplicate, too_similar) are injected via `extra_findings` before Stage 1 executes.

### Policy Gate
Portuguese-language rule set (v2.0.0) with segment-aware rules (health/fitness/beauty). Every result includes `internal_notice`: _"does NOT guarantee approval by Meta Ads"_.

BLOCKED: only owner can override when `ALLOW_BLOCKED_OVERRIDE=true` (disabled by default). Override requires `override_blocked=true` + mandatory comment. All overridden check IDs recorded in `Approval.overridden_check_ids`.

### Approval workflow
```
awaiting_approval → approved   (owner/admin; comment optional)
awaiting_approval → rejected   (owner/admin; comment required)
awaiting_approval → variation_queued (owner/admin; creates new GeneratedCreative with status=queued)
blocked → [common flow blocked]
blocked → approved  (owner only; ALLOW_BLOCKED_OVERRIDE=true; override_blocked=true; comment required)
```

### HMAC signed URLs
`GET /assets/{token}` — unauthenticated (HMAC token is the auth). No JWT cookie needed. Allows `<img src>` tags in the frontend without CORS complications. Token contains org_id, key, expiry, HMAC-SHA256 signature. Tampering → 404.

## Phase 3 additions

### Analysis segregation
`CreativeAnalysis` stores four strictly separate knowledge types:
- **observations** — visual facts (`ObservationItem`: text + category)
- **metric_facts** — metric-derived facts (`MetricFactItem`: text + metric + value)
- **performance_hypotheses** — unproven candidates (`PerformanceHypothesisItem`: statement + primary_variable + confidence)
- **limitations** — what the model doesn't know (string list)

No causal claims are made. Confidence is clamped to [0,1].

### Analysis idempotency
Each analysis has an `input_hash` = sha256(model + provider + image_path + metrics + request_fields). Calling analyze again with the same inputs returns the existing row. `force=True` always creates a new append-versioned row (`analysis_version` increments per source_ad).

### Prompt injection defense
Ad copy is wrapped in `<untrusted_ad_data>` XML delimiters in the Claude prompt. `_sanitise()` strips any `</untrusted_ad_data>` attempt from the copy before insertion.

### PromptVersion immutability
`revise` computes `content_hash = sha256(prompt_text)`. If the hash matches the parent's hash, a 409 is returned — no duplicate versions are created.

### Traceability chain
`SourceAd → CreativeAnalysis → CreativeHypothesis → PromptTemplate → PromptVersion`

## Data model summary (Phase 3)

```
Organization
  └── User (role: owner/admin/viewer)
  └── IntegrationCredential (encrypted)
  └── Product
        └── BrandProfile
  └── SourceAd
        └── PerformanceSnapshot
        └── CreativeAnalysis  [+input_hash, analysis_version, observations,
        │                       metric_facts, limitations, performance_hypotheses,
        │                       parameters, cost, latency, repaired]
        │     └── CreativeHypothesis  [statement, confidence, status]
        └── PromptTemplate  [+hypothesis_id FK]
              └── PromptVersion (versioned, immutable)  [+content_hash, author_type, target_model]
                    └── GeneratedCreative  [+storage_key, storage_backend, phash, variation_of_id]
                          └── CreativeAsset (role: original/derivative/thumbnail)
                          └── QualityCheck
                          └── PolicyCheck
                          └── Approval  [+action, overridden_check_ids]
                          └── PublishedAd (dry_run=True in Phase 1)
  └── Experiment
        └── ExperimentVariant
  └── AuditLog
```

## API surface (Phase 3)

| Method | Path | Description |
|---|---|---|
| POST | `/auth/login` | Email/password → JWT cookie |
| POST | `/auth/logout` | Clear cookie |
| GET | `/auth/me` | Current user |
| GET/POST | `/products` | List / create products |
| GET/POST | `/brand` | List / create brand profiles |
| GET | `/source-ads` | List historical ads |
| GET | `/source-ads/{id}` | Ad detail with snapshots |
| POST | `/source-ads/{id}/analyze` | Analyze ad (mock or real); idempotent by input_hash |
| GET | `/source-ads/{id}/analyses` | All analysis versions for an ad |
| GET | `/analyses/{id}` | Full analysis detail (all 30+ fields) |
| POST | `/prompts/generate` | Create template + v1 |
| GET | `/prompts` | List templates with filters |
| GET | `/prompts/{template_id}` | Template detail + latest version + count |
| POST | `/prompts/{template_id}/revise` | Create new version (409 on identical hash) |
| GET | `/prompts/{template_id}/versions` | All versions for a template |
| GET | `/prompt-versions/{id}` | Version detail |
| GET | `/prompt-versions/{id}/diff/{other}` | Unified diff + field changes |
| POST | `/creatives` | Generate image (mock) |
| GET | `/creatives/{id}` | Creative detail |
| POST | `/creatives/{id}/quality-check` | Run quality + policy checks |
| POST | `/creatives/{id}/approve` | Human approval |
| POST | `/creatives/{id}/reject` | Reject with comment |
| POST | `/publish/meta/dry-run` | Simulate publish (DRY_RUN) |
| GET | `/healthz` | Liveness probe |
| GET | `/readyz` | Readiness probe |
