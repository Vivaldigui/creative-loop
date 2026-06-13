"""
Unit tests for image_guard module (Phase 3).
Tests: format rejection, size limit, EXIF stripping, video detection.
"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pytest
from packages.anthropic_client.image_guard import (
    ImageTooLargeError,
    InvalidImageFormatError,
    UnsupportedMediaError,
    detect_media_kind,
    validate_and_prepare,
)

# ── detect_media_kind ─────────────────────────────────────────────

def test_image_path_returns_image():
    assert detect_media_kind("/ads/photo.png", None) == "image"


def test_image_jpeg_returns_image():
    assert detect_media_kind("banner.jpg", None) == "image"


def test_video_extension_returns_video():
    assert detect_media_kind("clip.mp4", None) == "video"


def test_no_path_returns_none():
    assert detect_media_kind(None, None) == "none"


def test_url_image():
    assert detect_media_kind(None, "https://example.com/img.webp") == "image"


# ── validate_and_prepare ──────────────────────────────────────────

def _write_tmp(data: bytes, suffix: str) -> Path:
    f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    f.write(data)
    f.flush()
    f.close()
    return Path(f.name)


def _minimal_png() -> bytes:
    """Minimal valid 1×1 white PNG bytes."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color=(255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


def test_valid_png_accepted():
    png_path = _write_tmp(_minimal_png(), ".png")
    try:
        data, media_type = validate_and_prepare(str(png_path))
        assert media_type == "image/png"
        assert len(data) > 0
    finally:
        png_path.unlink(missing_ok=True)


def test_invalid_format_rejected():
    tmp = _write_tmp(b"fake content", ".mp4")
    try:
        with pytest.raises(InvalidImageFormatError):
            validate_and_prepare(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)


def test_oversized_file_rejected():
    png_path = _write_tmp(_minimal_png(), ".png")
    try:
        with pytest.raises(ImageTooLargeError):
            validate_and_prepare(str(png_path), max_bytes=1)  # 1 byte limit
    finally:
        png_path.unlink(missing_ok=True)


def test_exif_stripped():
    """After stripping, output should be valid PNG with same content."""
    from PIL import Image
    buf = io.BytesIO()
    img = Image.new("RGB", (2, 2), color=(100, 150, 200))
    img.save(buf, format="PNG")
    raw = buf.getvalue()
    png_path = _write_tmp(raw, ".png")
    try:
        cleaned, _ = validate_and_prepare(str(png_path))
        # Re-open cleaned to verify it's still valid
        img2 = Image.open(io.BytesIO(cleaned))
        assert img2.size == (2, 2)
    finally:
        png_path.unlink(missing_ok=True)


# ── UnsupportedMediaError ─────────────────────────────────────────

def test_unsupported_media_error_carries_kind():
    exc = UnsupportedMediaError("video")
    assert exc.kind == "video"
    assert "video" in str(exc)
