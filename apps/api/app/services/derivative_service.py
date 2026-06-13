"""
Derivative image generation — resize originals to standard ad formats without distortion.

Strategy:
  - Same aspect ratio (within 1%): plain resize (LANCZOS, no upscale beyond original)
  - Different ratio: pad with brand/white background (fit_strategy="pad")
  - crop option available via explicit request

Thumbnails are always padded squares at THUMBNAIL_MAX_PX.
"""
from __future__ import annotations

import io

SUPPORTED_FORMATS: dict[str, tuple[int, int]] = {
    "1080x1080": (1080, 1080),
    "1080x1350": (1080, 1350),
    "1080x1920": (1080, 1920),
    "1200x628": (1200, 628),
}


class DerivativeResult:
    __slots__ = ("data", "width", "height", "fit_strategy", "format_label", "file_size_bytes")

    def __init__(
        self,
        data: bytes,
        width: int,
        height: int,
        fit_strategy: str,
        format_label: str,
    ) -> None:
        self.data = data
        self.width = width
        self.height = height
        self.fit_strategy = fit_strategy
        self.format_label = format_label
        self.file_size_bytes = len(data)


def make_derivative(
    original_bytes: bytes,
    target_w: int,
    target_h: int,
    format_label: str,
    *,
    bg_color: tuple[int, int, int] = (255, 255, 255),
    allow_upscale: bool = False,
) -> DerivativeResult:
    """Resize original to (target_w × target_h) without distortion."""
    from PIL import Image

    img = Image.open(io.BytesIO(original_bytes)).convert("RGB")
    orig_w, orig_h = img.size

    orig_ratio = orig_w / orig_h
    tgt_ratio = target_w / target_h

    if abs(orig_ratio - tgt_ratio) < 0.01:
        # Same aspect ratio — just resize (never upscale)
        new_w = min(target_w, orig_w) if not allow_upscale else target_w
        new_h = min(target_h, orig_h) if not allow_upscale else target_h
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        strategy = "none"
    else:
        # Pad with background color (letterbox)
        scale = min(target_w / orig_w, target_h / orig_h)
        if not allow_upscale:
            scale = min(scale, 1.0)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        scaled = img.resize((new_w, new_h), Image.LANCZOS)
        canvas = Image.new("RGB", (target_w, target_h), bg_color)
        x = (target_w - new_w) // 2
        y = (target_h - new_h) // 2
        canvas.paste(scaled, (x, y))
        resized = canvas
        strategy = "pad"

    buf = io.BytesIO()
    resized.save(buf, format="PNG", optimize=True)
    return DerivativeResult(
        data=buf.getvalue(),
        width=resized.width,
        height=resized.height,
        fit_strategy=strategy,
        format_label=format_label,
    )


def make_thumbnail(
    original_bytes: bytes,
    max_px: int = 512,
    bg_color: tuple[int, int, int] = (255, 255, 255),
) -> DerivativeResult:
    """Produce a square thumbnail ≤ max_px × max_px."""
    return make_derivative(
        original_bytes,
        max_px,
        max_px,
        format_label="thumb",
        bg_color=bg_color,
    )


def validate_file_size(data: bytes, max_mb: float) -> bool:
    """Return True if within limit."""
    return len(data) / (1024 * 1024) <= max_mb
