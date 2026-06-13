"""Unit tests for quality engine."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from packages.quality_engine.engine import (
    RESULT_BLOCKED,
    RESULT_PASS,
    RESULT_WARNING,
    QualityEngine,
)
from PIL import Image


def _write_png(path: Path, w: int = 1080, h: int = 1080) -> None:
    """Write a real valid PNG to path."""
    img = Image.new("RGB", (w, h), color=(180, 180, 180))
    img.save(str(path), format="PNG")


def test_missing_file_is_blocked():
    engine = QualityEngine()
    result = engine.check(file_path="/nonexistent/path/image.png")
    assert result.result == RESULT_BLOCKED
    assert any(f.check == "file_exists" for f in result.findings)


def test_valid_image_passes(tmp_path):
    img = tmp_path / "test.png"
    _write_png(img)
    result = QualityEngine(cv_enabled=False).check(file_path=str(img), width=1080, height=1080, prompt_text="A test prompt")
    assert result.result == RESULT_PASS


def test_nonstandard_dimensions_warn(tmp_path):
    img = tmp_path / "test.png"
    _write_png(img, w=800, h=600)
    result = QualityEngine(cv_enabled=False).check(file_path=str(img), width=800, height=600, prompt_text="test")
    assert result.result == RESULT_WARNING
    assert any(f.check == "dimensions" for f in result.findings)


def test_invalid_format_is_blocked(tmp_path):
    """Write a PNG but give it a .bmp extension — path-based format check should block it."""
    img = tmp_path / "test.bmp"
    # Write real PNG data but .bmp path — QualityEngine checks extension on file_path
    _write_png(Path(tmp_path / "real.png"))
    (tmp_path / "real.png").rename(img)
    result = QualityEngine(cv_enabled=False).check(file_path=str(img), width=1080, height=1080, prompt_text="test")
    # .bmp extension → format warning/block from path check
    assert any(f.check == "format" for f in result.findings)
    assert result.result in (RESULT_WARNING, RESULT_BLOCKED)
