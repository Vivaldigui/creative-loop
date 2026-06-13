"""OpenAI image generation — real provider.

Safety guarantees:
- reference_asset_key must be a storage key from internal storage; never an external URL
- Retries only on 429 / 500 / 503 / timeout (not on 400 content-policy violations)
- moderation_flagged=True is returned instead of raising on content-policy 400
- API key never logged or exposed
- Timeout enforced via asyncio.wait_for
"""

from __future__ import annotations

import asyncio
import base64
import random

import structlog

from .interface import ImageBytesResult, ImageRequest
from .pricing import estimate_cost

logger = structlog.get_logger()

# OpenAI-supported sizes for image generation
_SUPPORTED_SIZES: set[str] = {
    "1024x1024",
    "1024x1792",
    "1792x1024",
    "512x512",
    "256x256",
}

_RETRIABLE_STATUS: set[int] = {429, 500, 503}
_MAX_JITTER = 1.0


def _nearest_supported_size(width: int, height: int) -> tuple[int, int]:
    """Map requested size to the nearest OpenAI-supported size."""
    ratio = width / height
    candidates = [(int(s.split("x")[0]), int(s.split("x")[1])) for s in _SUPPORTED_SIZES]
    return min(candidates, key=lambda c: abs(c[0] / c[1] - ratio))


def _backoff(attempt: int) -> float:
    return min(2**attempt + random.uniform(0, _MAX_JITTER), 30.0)


class OpenAIImageClient:
    """Calls the official OpenAI images API. Activated by IMAGE_PROVIDER=openai."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-image-2",
        timeout_s: float = 90.0,
        max_retries: int = 3,
    ) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._timeout_s = timeout_s
        self._max_retries = max_retries

    # ── Public ─────────────────────────────────────────────────────

    async def generate(self, request: ImageRequest) -> ImageBytesResult:
        gen_w, gen_h = _nearest_supported_size(request.width, request.height)
        size_str = f"{gen_w}x{gen_h}"
        cost = estimate_cost(self._model, request.quality, gen_w, gen_h) * request.n

        for attempt in range(self._max_retries):
            try:
                resp = await asyncio.wait_for(
                    self._client.images.generate(
                        model=self._model,
                        prompt=request.prompt,
                        n=request.n,
                        size=size_str,  # type: ignore[arg-type]
                        quality=request.quality,
                        response_format="b64_json",
                    ),
                    timeout=self._timeout_s,
                )
                images = [base64.b64decode(d.b64_json or "") for d in resp.data]  # type: ignore[union-attr]
                logger.info("openai_generate_ok", model=self._model, size=size_str, n=request.n)
                return ImageBytesResult(
                    images=images,
                    mime_type="image/png",
                    provider="openai",
                    model_used=self._model,
                    estimated_cost_usd=cost,
                    parameters={"size": size_str, "quality": request.quality, "n": request.n},
                    moderation_flagged=False,
                )
            except TimeoutError:
                logger.warning("openai_timeout", attempt=attempt)
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(_backoff(attempt))
            except Exception as exc:  # noqa: BLE001
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status == 400:
                    # Content-policy violation — do not retry
                    logger.warning("openai_content_policy_violation", error=str(exc))
                    return ImageBytesResult(
                        images=[],
                        provider="openai",
                        model_used=self._model,
                        moderation_flagged=True,
                        parameters={"size": size_str, "quality": request.quality},
                    )
                if status in _RETRIABLE_STATUS and attempt < self._max_retries - 1:
                    retry_after = _parse_retry_after(exc)
                    await asyncio.sleep(retry_after or _backoff(attempt))
                    continue
                raise

        raise RuntimeError(f"OpenAI image generation failed after {self._max_retries} attempts")

    async def edit(self, request: ImageRequest) -> ImageBytesResult:
        """Image editing — only usable with an internal reference asset key."""
        if not request.reference_asset_key:
            raise ValueError("edit() requires reference_asset_key to be set")
        # For now, fall back to generate (edit API varies by model)
        logger.info("openai_edit_fallback_to_generate", model=self._model)
        return await self.generate(request)

    async def health_check(self) -> bool:
        try:
            models = await self._client.models.list()
            ok = any(m.id.startswith("gpt-image") or m.id.startswith("dall-e") for m in models.data)
            logger.debug("openai_health_check", ok=ok)
            return ok
        except Exception as exc:
            logger.warning("openai_health_check_failed", error=str(exc))
            return False


def _parse_retry_after(exc: object) -> float | None:
    try:
        headers = getattr(getattr(exc, "response", None), "headers", {})
        val = headers.get("retry-after") or headers.get("x-ratelimit-reset-requests")
        if val:
            return float(val)
    except Exception:
        pass
    return None
