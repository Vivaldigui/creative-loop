from __future__ import annotations

import io

from .interface import ImageBytesResult, ImageRequest


class MockImageClient:
    """Generates labeled PNG placeholders using Pillow — zero cost, zero external calls."""

    async def generate(self, request: ImageRequest) -> ImageBytesResult:
        return self._make_images(request, label="[MOCK PROVIDER]")

    async def edit(self, request: ImageRequest) -> ImageBytesResult:
        return self._make_images(request, label="[MOCK EDIT]")

    async def health_check(self) -> bool:
        return True

    # ── Internals ─────────────────────────────────────────────────

    def _make_images(self, request: ImageRequest, label: str) -> ImageBytesResult:
        from PIL import Image, ImageDraw, ImageFont

        images: list[bytes] = []
        for i in range(request.n):
            img = Image.new("RGB", (request.width, request.height), color=(220, 220, 220))
            draw = ImageDraw.Draw(img)
            draw.rectangle(
                [4, 4, request.width - 5, request.height - 5],
                outline=(180, 180, 180),
                width=3,
            )
            lines = [
                "[FICTITIOUS IMAGE]",
                label,
                f"{request.width}×{request.height}",
                f"Variant {i + 1}/{request.n}",
                request.prompt[:50] + ("…" if len(request.prompt) > 50 else ""),
            ]
            y = request.height // 2 - 80
            for line in lines:
                try:
                    font = ImageFont.load_default(size=max(14, request.width // 36))
                except TypeError:
                    font = ImageFont.load_default()
                bbox = draw.textbbox((0, 0), line, font=font)
                x = max(0, (request.width - (bbox[2] - bbox[0])) // 2)
                draw.text((x, y), line, fill=(80, 80, 80), font=font)
                y += 36

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            images.append(buf.getvalue())

        return ImageBytesResult(
            images=images,
            mime_type="image/png",
            provider="mock",
            model_used="mock-pillow",
            estimated_cost_usd=0.0,
            parameters={"n": request.n, "prompt_length": len(request.prompt)},
            moderation_flagged=False,
        )
