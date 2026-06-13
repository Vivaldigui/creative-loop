"""Phase 4 quality engine tests — bytes-first API, CV checks, extra_findings injection."""
from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from packages.quality_engine.engine import (
    RESULT_BLOCKED,
    RESULT_PASS,
    RESULT_WARNING,
    QualityEngine,
    QualityFinding,
)


def _png(w: int = 1080, h: int = 1080, color: tuple = (180, 180, 180)) -> bytes:
    img = Image.new("RGB", (w, h), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── bytes API ─────────────────────────────────────────────────────

def test_bytes_pass_with_standard_dimensions():
    data = _png(1080, 1080)
    result = QualityEngine(cv_enabled=False).check(
        data=data, width=1080, height=1080, prompt_text="A test prompt"
    )
    assert result.result == RESULT_PASS


def test_bytes_none_returns_blocked():
    result = QualityEngine(cv_enabled=False).check(data=None, file_path="")
    assert result.result == RESULT_BLOCKED
    assert any(f.check == "file_exists" for f in result.findings)


def test_nonstandard_dimensions_warning():
    data = _png(800, 600)
    result = QualityEngine(cv_enabled=False).check(
        data=data, width=800, height=600, prompt_text="Test"
    )
    assert result.result == RESULT_WARNING
    assert any(f.check == "dimensions" for f in result.findings)


def test_no_prompt_is_warning():
    data = _png()
    result = QualityEngine(cv_enabled=False).check(data=data, width=1080, height=1080)
    assert any(f.check == "prompt_present" for f in result.findings)
    assert result.result in (RESULT_WARNING, RESULT_BLOCKED)


# ── extra_findings injection ──────────────────────────────────────

def test_extra_findings_injected_into_result():
    extra = [QualityFinding(check="hash_duplicate", severity="blocked", detail="Dup.")]
    data = _png()
    result = QualityEngine(cv_enabled=False).check(
        data=data, width=1080, height=1080, prompt_text="Ad",
        extra_findings=extra,
    )
    assert result.result == RESULT_BLOCKED
    assert any(f.check == "hash_duplicate" for f in result.findings)


def test_extra_warning_finding_contributes():
    extra = [QualityFinding(check="too_similar", severity="warning", detail="Similar.")]
    data = _png()
    result = QualityEngine(cv_enabled=False).check(
        data=data, width=1080, height=1080, prompt_text="Ad",
        extra_findings=extra,
    )
    assert any(f.check == "too_similar" for f in result.findings)
    assert result.result in (RESULT_WARNING, RESULT_BLOCKED)


# ── CV checks ────────────────────────────────────────────────────

def test_cv_blur_detects_flat_image():
    """A uniformly colored image has zero sharpness — should be flagged as blurry."""
    data = _png(1080, 1080, color=(128, 128, 128))  # perfectly flat = blurry
    result = QualityEngine(cv_enabled=True).check(
        data=data, width=1080, height=1080, prompt_text="Test"
    )
    assert any(f.check == "image_quality_blur" for f in result.findings)


def test_cv_disabled_no_cv_findings():
    """With cv_enabled=False, CV checks (blur, margin) must not appear."""
    data = _png()
    result = QualityEngine(cv_enabled=False).check(
        data=data, width=1080, height=1080, prompt_text="Ad"
    )
    cv_checks = [f for f in result.findings if f.checker_type == "cv"]
    assert cv_checks == []


# ── checker_type field ────────────────────────────────────────────

def test_findings_have_checker_type():
    extra = [QualityFinding(check="x", severity="warning", detail=".", checker_type="deterministic")]
    data = _png()
    result = QualityEngine(cv_enabled=False).check(
        data=data, width=1080, height=1080, prompt_text="Ad",
        extra_findings=extra,
    )
    for f in result.findings:
        assert f.checker_type in ("deterministic", "cv", "ai")
