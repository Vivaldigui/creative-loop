# OpenAI Image Generation Setup

## Overview

Creative Loop uses OpenAI's image generation API (gpt-image-2 / dall-e-3) to produce ad creatives.
The system operates in two modes:

- **Mock mode** (default): zero cost, zero external calls — uses Pillow to render labeled placeholder images.
- **OpenAI mode**: activated only when `OPENAI_API_KEY` is explicitly set.

## Configuration

Add to your `.env` file:

```env
# Required for real image generation
OPENAI_API_KEY=sk-...

# Optional overrides (defaults shown)
IMAGE_PROVIDER=openai           # mock | openai
OPENAI_IMAGE_MODEL=gpt-image-2  # gpt-image-2 | dall-e-3
OPENAI_IMAGE_QUALITY=standard   # standard | hd
OPENAI_TIMEOUT_S=90.0
OPENAI_MAX_RETRIES=3
IMAGE_MAX_VARIATIONS=4
```

If `OPENAI_API_KEY` is absent or empty, the system automatically falls back to the mock provider regardless of `IMAGE_PROVIDER`.

## API Key Security

- The key is never logged, even at DEBUG level.
- The key never appears in audit logs or database records.
- The key is never included in API responses or error messages.
- Generation parameters (model, quality, size) are recorded; the key is not.

## Size Mapping

OpenAI supports a limited set of image sizes. The real provider maps the requested dimensions to the nearest supported size:

| Requested       | Mapped to      |
|-----------------|----------------|
| 1080×1080       | 1024×1024      |
| 1080×1350       | 1024×1024      |
| 1080×1920       | 1024×1792      |
| 1200×628        | 1792×1024      |

After generation, the `derivative_service` handles resizing to the exact ad format dimensions without distortion (pad strategy).

## Retry Policy

| HTTP Status | Behavior       |
|-------------|----------------|
| 429         | Retry with exponential backoff (up to `OPENAI_MAX_RETRIES`) |
| 500/503     | Retry with exponential backoff |
| 400         | No retry — content policy violation → `moderation_flagged=True` |
| Other 4xx   | No retry — raise immediately |

## Cost Estimation

Cost estimates (USD) are stored on every `GeneratedCreative` record. They are approximate and based on the published OpenAI pricing table at the time of this release. See `packages/openai_image_client/pricing.py`.

| Model         | Quality  | Size       | Estimated cost |
|---------------|----------|------------|----------------|
| gpt-image-2   | standard | 1024×1024  | $0.040         |
| gpt-image-2   | hd       | 1024×1024  | $0.080         |
| dall-e-3      | standard | 1024×1024  | $0.040         |
| dall-e-3      | hd       | 1024×1024  | $0.080         |

**Note:** These are estimates. Verify with the OpenAI billing dashboard.

## Mock Provider

The mock provider (default) is suitable for development, CI/CD, and demos:

- Generates real PNG files with dimensions matching the request.
- Labels images with "[FICTITIOUS IMAGE]" and "[MOCK PROVIDER]" so they can never be mistaken for real content.
- `estimated_cost_usd = 0.0` always.
- `is_fictitious = True` on all generated creatives.
- Supports `n` variations (distinct Pillow renders, unique pHash per variant is not guaranteed for very similar prompts).

## Running a Full Local Test

```bash
# Start API with mock provider (default)
cd apps/api
uvicorn app.main:app --reload

# Generate a creative
curl -X POST http://localhost:8000/creatives \
  -H "Content-Type: application/json" \
  -b "session=..." \
  -d '{"prompt_version_id": "<uuid>", "width": 1080, "height": 1080}'

# Check the approval queue
curl http://localhost:8000/approvals -b "session=..."
```

## Switching to Real OpenAI

1. Set `OPENAI_API_KEY=sk-...` in `.env`
2. Set `IMAGE_PROVIDER=openai`
3. Restart the API

The system will use the real provider for new generations. Existing mock-generated creatives are not affected.

## Limitations

- The OpenAI provider does not support image editing in Phase 4 MVP (`mode=edit` falls back to generation).
- AI quality checks (Stage 3 of the Quality Engine) are not implemented in Phase 4.
- The `reference_asset_key` parameter is reserved for future inpainting support.
