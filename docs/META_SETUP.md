# Meta Marketing API — Setup Guide

## Overview

The Creative Loop platform imports campaign/ad/performance data from the Meta Marketing API in **read-only** mode.
No ads are created, modified, activated, or deleted by this integration. The only OAuth scope required is `ads_read`.

---

## Environment Variables

Add to `.env` (never commit this file):

```env
META_PROVIDER=real          # use "mock" (default) during development/tests
META_APP_ID=<your_app_id>
META_APP_SECRET=<your_app_secret>
META_ACCESS_TOKEN=<long_lived_token>
META_AD_ACCOUNT_ID=act_<your_account_id>
META_GRAPH_API_VERSION=v21.0
META_PAGE_LIMIT=200
META_MAX_RETRIES=5
META_RATE_LIMIT_THRESHOLD=85
META_SYNC_INCREMENTAL_DAYS=30
META_SYNC_HISTORY_DATE_START=2024-01-01
```

`META_PROVIDER=mock` is the default. With mock, all imported data is synthetic and marked `is_fictitious=true`.
Switch to `real` only after obtaining a valid token.

---

## Required Permissions

| Scope | Purpose |
|---|---|
| `ads_read` | Read campaigns, ad sets, ads, creatives, images, and insights |

**Do NOT grant:**
- `ads_management` — allows write calls; violates least-privilege
- `business_management` — unnecessary
- Any publish/create scope

---

## Creating a Meta App and Token

1. Go to [developers.facebook.com](https://developers.facebook.com) and create a **Business** app.
2. Add the **Marketing API** product.
3. Under **App Settings → Advanced**, note your App ID and App Secret.
4. Generate a **User Access Token** with scope `ads_read` via the Graph API Explorer.
5. Exchange it for a **Long-Lived Token** (valid for 60 days):
   ```
   GET /oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id={app_id}
     &client_secret={app_secret}
     &fb_exchange_token={short_lived_token}
   ```
6. Set `META_ACCESS_TOKEN` to the resulting long-lived token.

### Token expiry

Long-lived tokens expire after ~60 days. To avoid sync failures:
- Implement token refresh before expiry (not yet automated in Phase 2).
- Monitor for `MetaAuthError` in logs — it indicates an expired or revoked token.

---

## Security: appsecret_proof

Every request includes an `appsecret_proof` parameter:
```
HMAC-SHA256(app_secret, access_token)
```
This is computed by `MetaGraphTransport` and never logged or stored. The `_redact()` helper strips
both `access_token` and `appsecret_proof` before any logging or database persistence.

---

## Rate Limiting

The transport monitors `x-business-use-case-usage` and `x-app-usage` response headers.
When any metric exceeds `META_RATE_LIMIT_THRESHOLD` (default: 85%), a warning is logged.

Error code classifications:
- **Auth errors** (190, 102, 10, 200, 803): not retried — indicates token issue
- **Rate limit errors** (4, 17, 32, 613, 80000, 80004): retried with increasing delay (up to 120s)
- **Server errors** (500–504): retried with exponential backoff

---

## Running an Import

### Via API (requires owner/admin role)

```bash
# Full historical import
curl -X POST http://localhost:8000/sync/meta/history \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{}'

# Incremental sync (last 30 days)
curl -X POST http://localhost:8000/sync/meta/incremental \
  -b cookies.txt \
  -d '{}'

# Check sync run status
curl http://localhost:8000/sync/meta/runs?limit=5 -b cookies.txt
```

### Via Frontend

Go to `/integrations` → "Importação de Dados" → click **Importar Histórico Completo** or **Sync Incremental**.

### Via Celery (automatic)

The Beat task `dispatch_meta_incremental_syncs` runs every hour automatically when `META_PROVIDER=real`.
It is skipped (no-op) when `META_PROVIDER=mock` to avoid polluting development databases.

---

## What Is Imported (Read-Only)

| Entity | Meta API Path |
|---|---|
| Ad Account | `/{account_id}?fields=...` |
| Campaigns | `/{account_id}/campaigns` |
| Ad Sets | `/{account_id}/adsets` |
| Ads + Creatives | `/{account_id}/ads?fields=creative{...}` |
| Ad Images | `/{account_id}/adimages` |
| Insights | `/{account_id}/insights` (chunked by month, GET only) |

Insights use monthly chunks to avoid the async report job (POST) pattern, keeping all calls as GET.

---

## What Is NOT Done

- Creating, activating, pausing, or deleting any ad object
- Changing budgets
- Calling any POST/PUT/DELETE endpoint on the Meta API
- Browser automation — only the official Graph API is used

Any non-GET call will raise `MetaWriteForbiddenError` immediately.

---

## Phase 5: DRY_RUN Publish Simulation

Phase 5 adds a full publication simulation mode. **No real Meta write calls are made at any point.**

### Key settings

```env
DRY_RUN=true                         # must stay true; Phase 6 enables real writes
REQUIRE_HUMAN_APPROVAL=true          # approval record required before simulation
MAX_DAILY_SPEND=200.0                # BRL; publish blocked if budget exceeds this
MAX_DAILY_NEW_ADS=3                  # max simulations per day per org
PUBLICATION_IDEMPOTENCY_TTL_HOURS=24 # how long an idempotency key is valid
```

### Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/publish/meta/validate` | Run guards + return check results; no persistence |
| `POST` | `/publish/meta/dry-run` | Full simulation: guards → simulate → persist attempt + audit |
| `POST` | `/publish/meta` | **501 Not Implemented** — real publish available in Phase 6 only |
| `POST` | `/publish/meta/drafts` | Create/update a publication draft |
| `GET` | `/publish/meta/drafts` | List drafts for the current org |
| `GET` | `/publication-drafts/{id}` | Draft detail with last attempt |
| `GET` | `/publication-attempts/{id}` | Attempt detail |

### Safety guarantees

1. **DryRunPublisher has no HTTP imports** — cannot make network calls.
2. **All simulated ads are PAUSED** — `status` field is forced by a Pydantic validator regardless of input.
3. **Simulated IDs are prefixed** `simulated_{type}_{hex12}` — cannot be confused with real Meta IDs.
4. **PENDING_* constants** replace unconfigured Meta IDs (page ID, ad account ID, pixel ID, etc.). Never invented IDs.
5. **Idempotency**: `(org_id, idempotency_key)` unique constraint. Same key + same payload → safe retry (200). Same key + different payload → conflict (409).
6. **Payload sanitization** strips `access_token`, `appsecret_proof`, `secret`, `token`, `key`, `password` before any DB storage or audit log.
7. **Dual AuditLog**: intent record written before simulation, result record after.
8. **SSRF guard**: landing URL hostname resolved; private IP ranges and metadata endpoints blocked.

### What Phase 5 does NOT do

- Call any Meta API endpoint (read or write)
- Create a real campaign, ad set, ad creative, or ad
- Upload any image to Meta
- Activate any ad (all simulated ads are PAUSED and never activate)
- Spend any money

---

## Phase 6: Real Meta Publish

Phase 6 enables actual ad creation via the Meta Marketing API. **Requires explicit opt-in with two separate flags.**

### Additional environment variables

```env
DRY_RUN=false                  # must be explicitly set to false
META_WRITE_ENABLED=true        # must be explicitly set to true
META_AD_ACCOUNT_ID=act_<id>   # must be a real, live ad account
META_PAGE_ID=<page_id>        # required for ad creative
META_PIXEL_ID=<pixel_id>      # required for conversion tracking
META_INSTAGRAM_ACTOR_ID=<id>  # optional; for Instagram placement
```

### Required additional permissions (for write)

| Scope | Purpose |
|---|---|
| `ads_read` | Read campaigns, adsets, ads, insights (existing) |
| `ads_management` | Create and manage campaigns, adsets, ads |
| `pages_read_engagement` | Read page info for ad creative |

**Token must be a System User Token** (not a personal user token) for production use. Personal tokens expire and cannot be automated safely.

### Endpoints (Phase 6)

| Method | Path | Auth required | Description |
|---|---|---|---|
| `POST` | `/publish/meta` | editor+ | Real publish (requires both interlock flags + `confirm_paused=true`) |
| `GET` | `/publication-attempts/{id}/status` | authenticated | Attempt detail with step-by-step progress |
| `GET` | `/published-ads` | authenticated | List published ads (filter by mode/status) |
| `GET` | `/published-ads/{id}` | authenticated | Single ad detail |
| `POST` | `/published-ads/{id}/refresh-status` | editor+ | Query Meta for current `effective_status` |
| `POST` | `/published-ads/{id}/activate` | **owner only** | Manual activation (PAUSED → ACTIVE); sends real spend |
| `POST` | `/published-ads/{id}/pause` | editor+ | Regular pause (ACTIVE → PAUSED) |
| `POST` | `/published-ads/{id}/emergency-pause` | **any auth user** | Emergency pause; no role or confirmation required |

### Manual test steps (no credentials required for CI)

The following test verifies the integration manually once real credentials are available:

```bash
# 1. Set up real credentials in .env
# 2. Run with real flags (NEVER commit these values)
export DRY_RUN=false
export META_WRITE_ENABLED=true
export META_PROVIDER=real

# 3. Create a creative and get it approved
# 4. Trigger publish via API
curl -X POST http://localhost:8000/publish/meta \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "creative_id": "<approved_creative_id>",
    "idempotency_key": "manual-test-001",
    "daily_budget_brl": 5.0,
    "landing_url": "https://your-site.com/offer",
    "confirm_paused": true,
    "campaign_name": "Manual Test Campaign"
  }'

# 5. Check status
curl http://localhost:8000/publication-attempts/<attempt_id>/status -b cookies.txt

# 6. Verify in Meta Ads Manager:
#    - Campaign exists with status PAUSED
#    - Ad Set exists with status PAUSED
#    - Ad exists with status PAUSED
#    - No spend has occurred

# 7. Emergency pause (if needed)
curl -X POST http://localhost:8000/published-ads/<ad_id>/emergency-pause -b cookies.txt

# 8. Clean up: delete test campaign in Meta Ads Manager (manual step)
```

### Phase 6 safety guarantees

1. **Two-flag interlock**: `DRY_RUN=false` AND `META_WRITE_ENABLED=true` — both required simultaneously.
2. **PAUSED enforcement**: all ads created as `PAUSED`. Pydantic validator + client guard + Meta response validation — three independent checks.
3. **Reconciliation**: idempotency tag embedded in resource names. If task restarts, existing resources are reused (not duplicated).
4. **No automatic activation**: `max_retries=0` on the Celery task that creates ads. Activation is always a separate manual action.
5. **Budget immutability**: budget is validated at publish time and re-validated at activation. Never increased automatically.
6. **Token safety**: `access_token` and `app_secret` never logged, never in DB, never in audit payloads.
7. **Manual review flag**: if Meta returns `effective_status != PAUSED` after create, `requires_manual_review=True` is set and a safe pause is attempted immediately.
8. **Emergency pause**: any authenticated user can trigger emergency pause with zero barriers.
