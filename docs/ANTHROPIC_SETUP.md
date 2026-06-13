# Anthropic (Claude) Setup — Phase 3

## Default mode: mock

`ANTHROPIC_PROVIDER=mock` (the default) returns structured deterministic analysis without any API calls or cost. All tests run against the mock.

## Switching to real Claude

### 1. Generate an API key

Go to [console.anthropic.com](https://console.anthropic.com) → API Keys → Create Key.

### 2. Set environment variables

```bash
# In apps/api/.env
ANTHROPIC_PROVIDER=real
ANTHROPIC_API_KEY=sk-ant-...

# Optional tuning (defaults shown)
ANTHROPIC_MODEL=claude-opus-4-8
ANTHROPIC_MAX_TOKENS=4096
ANTHROPIC_TEMPERATURE=0.3
ANTHROPIC_TIMEOUT_S=60.0
ANTHROPIC_MAX_RETRIES=3
ANTHROPIC_MAX_IMAGE_MB=5.0

# Optional cost tracking (USD per million tokens)
ANTHROPIC_PRICE_INPUT_PER_MTOK=15.0
ANTHROPIC_PRICE_OUTPUT_PER_MTOK=75.0
```

### 3. Restart the API

```bash
uvicorn app.main:app --reload
```

### 4. Trigger analysis

```
POST /source-ads/{id}/analyze
```

The API will call Claude with the ad image (if present) and aggregated metrics. The response includes `provider: "real"` and `model_used`.

---

## Security notes

- The API key is **never logged** — not in structlog, not in AuditLog payloads.
- Ad copy is sandboxed in `<untrusted_ad_data>` XML delimiters. Claude is instructed to treat its contents as untrustworthy.
- `_sanitise()` strips any `</untrusted_ad_data>` attempt in the copy before it enters the prompt.
- Images are validated (format: png/jpeg/webp/gif; size: ≤ `ANTHROPIC_MAX_IMAGE_MB`). EXIF metadata is stripped via Pillow before sending.
- Only token counts, latency, and status are recorded in the database — never the raw image bytes or copy text.

---

## Response structure

The real provider returns the same `AnalysisResult` schema as the mock. The model is instructed to use the `emit_analysis` tool (tool_use) to return structured JSON.

If the JSON cannot be parsed, `_repair_json()` is attempted. If repair succeeds, `repaired=True` is set on the analysis. If it fails, `status=failed` and `error_detail` records the exception.

### Segregated knowledge types

| Field | Type | What it contains |
|---|---|---|
| `observations` | `ObservationItem[]` | Visual facts only — composition, color, text, product, attention, style |
| `metric_facts` | `MetricFactItem[]` | Facts derived from metrics — never causality claims |
| `performance_hypotheses` | `PerformanceHypothesisItem[]` | Testable hypotheses with confidence [0,1] |
| `limitations` | `string[]` | What the model cannot assess |

**No causal claims.** The prompt explicitly instructs the model not to assert causality (e.g., "this caused the high CTR"). Hypotheses must be phrased as testable propositions.

---

## Cost tracking

If `ANTHROPIC_PRICE_INPUT_PER_MTOK` and `ANTHROPIC_PRICE_OUTPUT_PER_MTOK` are set, `estimated_cost_usd` is computed per analysis. Built-in price table covers:

| Model | Input ($/MTok) | Output ($/MTok) |
|---|---|---|
| claude-opus-4-8 | 15.00 | 75.00 |
| claude-sonnet-4-6 | 3.00 | 15.00 |
| claude-haiku-4-5-20251001 | 0.80 | 4.00 |

---

## Idempotency

Calling `POST /source-ads/{id}/analyze` with the same ad state returns the existing analysis without a new API call. The `input_hash` is sha256 of: model + provider + image_path + aggregated metrics + request fields.

Use `{"force": true}` in the request body to force a new analysis (new `analysis_version` row).

---

## Retry policy

The real provider retries on:
- HTTP 429 (rate limit) — respects `Retry-After` header, otherwise exponential backoff
- HTTP 529 (overload) — exponential backoff
- `asyncio.TimeoutError` — up to `ANTHROPIC_MAX_RETRIES` attempts

Auth errors (401/403) and validation errors are never retried.
