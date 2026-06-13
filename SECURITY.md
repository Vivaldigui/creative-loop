# Security Model — Creative Loop

## Secrets management

- All secrets are environment variables only — never hardcoded, logged, or committed.
- `.env.example` contains only `PREENCHER_*` placeholders.
- `.env` is gitignored.
- `SECRET_KEY`: HS256 JWT signing key. Generate with `python -c "import secrets; print(secrets.token_hex(32))"`.
- `ENCRYPTION_KEY`: Fernet symmetric key for credential encryption. Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

## Authentication

- JWT (HS256) in httpOnly, SameSite=Lax cookie — never exposed to JavaScript.
- Token payload: `sub` (user_id), `org` (organization_id), `role`, `exp`, `jti`.
- Passwords hashed with Argon2 via passlib.

## Authorization (RBAC)

- Roles: `owner`, `admin`, `editor`, `viewer` (descending privilege).
- All destructive operations (`POST /products`, `POST /brand`, `POST /creatives/{id}/approve`) require `owner` or `admin`.
- Multi-tenancy: every DB query filters by `organization_id` derived from the JWT.

## Credential storage

- Third-party API credentials (Meta, OpenAI, Anthropic) are stored Fernet-encrypted.
- Decryption key (`ENCRYPTION_KEY`) is only in env — never in the DB, logs, or responses.
- Tokens and keys are never sent to the frontend.

## Financial safety

- `DRY_RUN=true` by default — no real Meta writes.
- `REQUIRE_HUMAN_APPROVAL=true` by default — approval required before any publish.
- `MAX_DAILY_SPEND` and `MAX_EXPERIMENT_BUDGET` are empty by default; publish is blocked until they are set.
- No budget can be increased automatically — requires human intervention.

## Ad publishing safety

- All Meta ads start as `PAUSED` — no ad is ever automatically activated.
- Every publish action writes to `AuditLog` before making any external call.
- Idempotency keys prevent duplicate publishes.
- Publish endpoint verifies: DRY_RUN flag, approval record, budget limits, idempotency.

## Policy enforcement

- `PolicyEngine` runs regex rules against prompt/copy text before any creative can be approved.
- `BLOCKED` result prevents approval → prevents publish.
- Rules cover: guarantee claims, medical treatment, before/after comparisons, false urgency, absolute superlatives.

## Prompt integrity

- Prompts are never overwritten. Each revision creates a new `PromptVersion` with a diff.
- `snapshot_prompt` in `Approval` is an immutable copy of the prompt text at the time of approval.

## Phase 4: Image generation and storage security

### API key handling
- `OPENAI_API_KEY` is only read from env; never stored in DB, never logged, never in audit payloads.
- `IMAGE_PROVIDER=mock` is the default — zero API cost unless explicitly switched to `openai`.
- The mock provider generates real Pillow PNGs marked `[FICTITIOUS IMAGE]`; no external call is made.

### File storage (LocalStorage)
- Files are stored at `<STORAGE_BASE_DIR>/<org_id>/<uuid>.<ext>` — org prefix prevents cross-tenant path traversal.
- `validate_key()` rejects keys with `..`, null bytes, leading slashes, and mismatched org prefix.
- Files are never served by raw path. All access goes through `GET /assets/{token}` with HMAC-SHA256 verification.
- HMAC token contains: `org_id`, `key`, `exp` (Unix timestamp). Tampering or expiry → 404.
- Default token TTL is configurable via `STORAGE_SIGNED_URL_TTL_SECONDS` (default: 3600 s).
- Original file is always preserved as a separate asset; derivatives never overwrite it.

### Deduplication and content integrity
- `sha256` exact-match deduplication: identical files are flagged as quality findings before storage.
- `pHash` near-duplicate detection (Hamming distance ≤ threshold): visually similar images are flagged.
- Approved content is immutable — `Approval` stores `snapshot_prompt` at approval time; content cannot be altered afterward.

### BLOCKED creative enforcement
- A creative with any BLOCKED quality or policy check **cannot** be approved via the standard flow.
- Override is gated by `ALLOW_BLOCKED_OVERRIDE=false` (default — disabled).
- When enabled: only `owner` role may override; `override_blocked=true` flag is required; comment is mandatory.
- All overridden check IDs are recorded in `Approval.overridden_check_ids` for audit purposes.
- `admin` and `viewer` roles cannot approve BLOCKED content under any flag value.

### WARNING confirmation
- Quality or policy findings with severity `warning` do not block approval but are surfaced in the UI.
- The `internal_notice` field is always returned by the policy-check and approvals endpoints:
  _"This platform does NOT guarantee approval by Meta Ads. Compliance is the advertiser's responsibility."_
- No code path ever claims or implies Meta Ads approval.

### Request-variation immutability
- `POST /creatives/{id}/request-variation` always creates a **new** `GeneratedCreative` record (status=queued).
- The original creative is automatically rejected — it cannot be approved after a variation is requested.
- No existing asset or check record is overwritten or deleted.

### No distortion guarantee
- Derivative images use the pad (letterbox) strategy — transparent/black padding is added rather than stretching pixels.
- Image aspect ratio is never altered; content is never cropped.

## Phase 5: DRY_RUN publish safety

### Zero real writes
- `DryRunPublisher` has **no HTTP imports** (`httpx`, `MetaGraphTransport` absent from the file). Even if incorrectly wired, it physically cannot make a network call.
- `RealMetaWriteClient` raises `MetaPublishDisabledError` on all 7 write methods (`create_campaign`, `create_adset`, `upload_image`, `create_ad_creative`, `create_ad`, `update_ad_status`, `update_budget`).
- `get_meta_publisher(dry_run=False)` raises `AssertionError` — the factory cannot return a real publisher.
- The real publish endpoint (`POST /publish/meta`) returns HTTP 501 Not Implemented until Phase 6.
- Critical automated test: `test_no_http_write_calls_during_dry_run` patches `httpx.AsyncClient.__init__` to raise — the test fails if any HTTP client is instantiated during DRY_RUN.

### PAUSED enforcement
- `status="PAUSED"` is set by a `@field_validator(mode="before")` on `CampaignPayload`, `AdSetPayload`, and `AdPayload` — runs before Pydantic validation, before `__init__`, and ignores any caller-supplied value. Passing `status="ACTIVE"` is silently overridden to `"PAUSED"`.

### Simulated ID naming
- All simulated IDs follow the pattern `simulated_{type}_{uuid4().hex[:12]}` (e.g. `simulated_campaign_a3b1c9d2e8f4`).
- No real Meta ID is ever invented. Unconfigured fields use named `PENDING_*` constants.

### Payload sanitization
- `_sanitize_payload()` strips any field whose key contains: `access_token`, `appsecret_proof`, `secret`, `token`, `key`, `password`. Replacement value is `***REDACTED***`.
- Sanitization is recursive — works on nested dicts.
- All stored payloads (`PublicationAttempt.checks`, `AuditLog.payload`) pass through this function before persistence.

### SSRF protection (landing URL guard)
- Landing URL resolved to IP at guard time.
- Blocked if IP is in: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.0.0/16`.
- Blocked if hostname contains: `169.254.169.254`, `metadata.google.internal`, `metadata.azure.internal`.
- Only `http://` and `https://` schemes pass; `ftp://`, `file://`, etc. are blocked.

### Idempotency security
- `(organization_id, idempotency_key)` database UniqueConstraint prevents duplicate attempts.
- Payload hash comparison detects key reuse with different content → 409 Conflict.
- Canonical hash: `sha256(json.dumps(sanitized_payload, sort_keys=True))` — resistant to key-order manipulation.

### Dual audit trail
- Two `AuditLog` records per dry-run: intent (before simulation) and result (after).
- Each record includes `correlation_id` (from `X-Correlation-ID` header or auto-UUID), `idempotency_key`, `approval_id`, `limits_checked`.
- Audit records are never deleted or updated.

## Phase 6: Real Meta publish safety

### Two-flag interlock
- Real writes require `DRY_RUN=false` AND `META_WRITE_ENABLED=true` — both flags in the same process.
- Neither flag alone enables real writes.
- Guards `guard_real_mode_enabled` and `guard_write_enabled` are the first two checks in `_REAL_GUARD_SEQUENCE`.

### PAUSED-only creation
- `CampaignPayload`, `AdSetPayload`, `AdPayload` validators force `status="PAUSED"` before init — no caller input can override this.
- `RealMetaWriteClient` asserts `payload["status"] == "PAUSED"` before every POST — a second independent check.
- After every create, `effective_status` from Meta's response is validated. If not `"PAUSED"`, `PublishedAd.requires_manual_review = True` and a safe pause is attempted immediately.

### Activation safety
- `POST /published-ads/{id}/activate` requires `owner` role (not admin, not viewer).
- Caller must pass `confirmation = meta_ad_id` — the actual Meta ad ID is the required confirmation string.
- Budget limits are re-validated at activation time.
- One HTTP call only (`update_ad_status`); no retry on activation.
- Two `AuditLog` records: intent + result.

### Emergency pause
- `POST /published-ads/{id}/emergency-pause` requires only a valid JWT — no role check, no confirmation.
- Priority design: minimal friction to stop a live ad.
- `AuditLog.emergency = True` is set — distinguishes emergency from regular pause in audit history.

### Celery task safety
- `publish_real_task` has `max_retries=0` — the task that creates real ads never retries automatically.
- `acks_late=True` + `reject_on_worker_lost=True` — task is re-queued if worker crashes before completing; reconciliation (`find_by_idempotency_tag`) prevents duplicate creates.
- All payload fields passed as individual parameters (not serialized blob) — no deserialization attack surface.

### Token and credential safety
- `access_token` and `app_secret` never logged, never stored in DB, never in AuditLog payloads.
- `WriteGraphTransport._redact()` strips `access_token`, `appsecret_proof`, and any field containing `key`, `token`, `secret`, `password` from log output.
- HMAC `appsecret_proof = HMAC_SHA256(app_secret, access_token)` — required by Meta for server-side calls.
- New `httpx.AsyncClient` created per request — no persistent session that could leak credentials between requests.

### Reconciliation and idempotency
- Every non-idempotent POST is preceded by `find_by_idempotency_tag()` search.
- Idempotency tag: short UUID suffix embedded in resource name — survives network errors and restarts.
- `MetaWriteAmbiguousError` raised when a non-idempotent POST fails after being sent — caller must reconcile (not retry blindly).
- Idempotent POSTs (e.g., `update_ad_status`) auto-retry up to `max_retries` and surface the original error.

### Budget immutability
- Budget is validated at publish time and re-validated at activation time.
- No code path ever increases `daily_budget_brl` automatically.
- Any budget change requires explicit human input and a new publish request.

## Phase 7: Experimentation and learning safety

### No automatic optimization actions
- **No fine-tuning, ever** — the loop never trains or tunes a model. It produces human-reviewed suggestions only.
- **No automatic image generation** — `NextRoundService` records `auto_image_generation: False` on every suggestion. No creative is generated without explicit human approval.
- **No automatic budget change** — `OptimizationDecision.suggested_action` is advisory; `executed_action` is filled only when a human acts. `DecisionService` never writes budget (`max_automatic_budget_increase_percent=0`).
- **No automatic publish** — `ExperimentSuggestion` starts `pending_approval`; it cannot trigger downstream generation or publication on its own.

### Conservative winner declaration
- `winner_candidate` is unreachable until **all** minimum criteria are satisfied: `min_impressions`, `min_spend`, `min_clicks`, `min_days`, `min_difference`, `min_confidence`, plus snapshot maturation (`maturation_window_days`).
- A `peeking_risk` limitation is always attached when an experiment is evaluated before its window ends — the platform never hides the statistical caveat of mid-flight peeking.
- **EXPLORATORY** experiments set `causal_attribution=False` always and can never reach `winner_candidate` (capped at `promising`). Only **CONTROLLED** single-variable experiments may attribute causality.
- Confidence is a Beta-Binomial posterior (pure math, no scipy) — deterministic and auditable.

### Single-variable isolation (CONTROLLED)
- `guard_controlled_single_variable` blocks `start` unless every test variant changes exactly one variable equal to `primary_variable`.
- `guard_has_baseline` blocks `start` when variants exist but none is `is_control` (it only warns for an empty draft).

### Learning lifecycle integrity
- Every `Learning` is created `provisional` — never `confirmed`.
- `provisional → confirmed` requires a human reviewer (`reviewed_by_id`, `reviewed_at`).
- `provisional → rejected` requires a mandatory `review_comment` (counter-evidence).
- No single learning is treated as definitive truth; `limitations` are stored alongside every learning, and `supersedes_id` records when a newer learning overrides an older one.

### Idempotent, non-retrying workers
- `collect_variant_metrics` upserts on `uq_variant_snapshot_key` (variant_id, date_start, date_stop, level, breakdown_key, attribution_window) — re-running any window never duplicates snapshots.
- All Phase 7 Celery tasks use `max_retries=0` and `acks_late=True`.
- Anomaly detectors (anomalous spend, zero conversions, rejected ads) flag experiments for human review; they never pause spend or change budget on their own.
- Beat schedules and report windows use `America/Sao_Paulo`.

### Append-only evaluation audit
- `ExperimentEvaluation` rows are insert-only — never updated or deleted. The full sequence of judgements (and any peeking) remains auditable.
- `AuditLog` records are written for create, start, stop, complete, decision, learning confirm/reject, and suggestion approve/reject.

### Embedding portability
- Learning embeddings are 128-d, stored as JSONB `list[float]` for SQLite/PostgreSQL portability (pgvector in production). In dev/tests a deterministic SHA256-based mock embedding is used — no external embedding API is called.

## Structural defenses

- No SSRF: external URLs validated before use (Phase 5 adds landing URL guard).
- Structured logging with secret redaction (structlog).
- `is_fictitious=True` on all seed data; fictitious banner on all frontend pages.
- File upload size and format limits in quality gate.
- Path traversal prevention in storage key validation (`validate_key()`).
