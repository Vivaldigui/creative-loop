"""Unit tests for derivative_service — resize strategies, no distortion guarantees."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image

from app.services.derivative_service import (
    make_derivative,
    make_thumbnail,
    validate_file_size,
)


def _png(w: int, h: int, color: tuple = (128, 64, 32)) -> bytes:
    """Return minimal valid PNG bytes of size w×h."""
    img = Image.new("RGB", (w, h), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── make_derivative ───────────────────────────────────────────────

def test_derivative_same_ratio_no_padding():
    """Square → square: same ratio → just resize, no pad."""
    data = _png(2160, 2160)
    result = make_derivative(data, 1080, 1080, "1080x1080", allow_upscale=True)
    assert result.width == 1080
    assert result.height == 1080
    assert result.fit_strategy == "none"


def test_derivative_different_ratio_uses_pad():
    """Square source → portrait target (1080×1350): must pad, not distort."""
    data = _png(1080, 1080)
    result = make_derivative(data, 1080, 1350, "1080x1350", allow_upscale=True)
    assert result.width == 1080
    assert result.height == 1350
    assert result.fit_strategy == "pad"


def test_derivative_output_is_valid_png():
    data = _png(1080, 1080)
    result = make_derivative(data, 1080, 1920, "1080x1920", allow_upscale=True)
    img = Image.open(io.BytesIO(result.data))
    assert img.format == "PNG"


def test_derivative_no_upscale_by_default():
    """Tiny image → large target, allow_upscale=False → capped at original size."""
    data = _png(100, 100)
    result = make_derivative(data, 1080, 1080, "1080x1080")
    # Width and height should be ≤ original 100
    assert result.width <= 100
    assert result.height <= 100


def test_derivative_landscape_source_to_portrait():
    """Landscape → portrait with pad: result must be target dimensions."""
    data = _png(1200, 628)
    result = make_derivative(data, 1080, 1920, "1080x1920", allow_upscale=True)
    assert result.width == 1080
    assert result.height == 1920
    assert result.fit_strategy == "pad"


def test_derivative_data_is_bytes():
    data = _png(1080, 1080)
    result = make_derivative(data, 1080, 1350, "1080x1350", allow_upscale=True)
    assert isinstance(result.data, bytes)
    assert len(result.data) > 0


# ── make_thumbnail ────────────────────────────────────────────────

def test_thumbnail_is_square():
    data = _png(1080, 1920)
    result = make_thumbnail(data, max_px=512)
    assert result.width == 512
    assert result.height == 512


def test_thumbnail_smaller_than_max():
    data = _png(1080, 1080)
    result = make_thumbnail(data, max_px=256)
    assert result.width <= 256
    assert result.height <= 256


def test_thumbnail_format_label():
    data = _png(1080, 1080)
    result = make_thumbnail(data, max_px=128)
    assert result.format_label == "thumb"


# ── validate_file_size ────────────────────────────────────────────

def test_file_size_ok():
    assert validate_file_size(b"x" * 1024, max_mb=1.0) is True


def test_file_size_exceeded():
    big = b"x" * (2 * 1024 * 1024)
    assert validate_file_size(big, max_mb=1.0) is False
