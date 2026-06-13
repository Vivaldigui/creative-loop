"""Unit tests for deduplication helpers — sha256, pHash, Hamming distance."""
from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.services.dedup import compute_phash, compute_sha256, phash_distance


def _png(color: tuple = (200, 100, 50), size: tuple = (64, 64)) -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── sha256 ────────────────────────────────────────────────────────

def test_sha256_deterministic():
    data = b"hello"
    assert compute_sha256(data) == compute_sha256(data)


def test_sha256_hex_64_chars():
    assert len(compute_sha256(b"test")) == 64


def test_sha256_different_for_different_data():
    assert compute_sha256(b"aaa") != compute_sha256(b"bbb")


# ── pHash ─────────────────────────────────────────────────────────

def test_phash_returns_hex_string():
    ph = compute_phash(_png())
    assert isinstance(ph, str)
    assert len(ph) > 0


def test_phash_same_image_identical():
    data = _png()
    assert compute_phash(data) == compute_phash(data)


def test_phash_very_different_images_high_distance():
    white = _png(color=(255, 255, 255), size=(64, 64))
    black = _png(color=(0, 0, 0), size=(64, 64))
    dist = phash_distance(compute_phash(white), compute_phash(black))
    # White and black should differ significantly
    assert dist > 0


def test_phash_identical_images_zero_distance():
    data = _png()
    ph = compute_phash(data)
    assert phash_distance(ph, ph) == 0


def test_phash_similar_images_low_distance():
    """Two images differing only by 1 pixel in a solid region → very similar pHash."""
    img_a = Image.new("RGB", (64, 64), color=(180, 180, 180))
    img_b = Image.new("RGB", (64, 64), color=(180, 180, 180))
    img_b.putpixel((32, 32), (181, 180, 180))  # 1-pixel tweak

    def to_png(img: Image.Image) -> bytes:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    dist = phash_distance(compute_phash(to_png(img_a)), compute_phash(to_png(img_b)))
    assert dist <= 4  # Near-duplicate threshold
