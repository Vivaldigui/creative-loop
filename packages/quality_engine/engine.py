from __future__ import annotations

import io
import pathlib
from typing import Literal

from pydantic import BaseModel

RESULT_PASS = "PASS"
RESULT_WARNING = "WARNING"
RESULT_BLOCKED = "BLOCKED"

VALID_FORMATS = {"png", "jpg", "jpeg", "webp"}
MAX_FILE_SIZE_MB = 30
VALID_DIMENSIONS = {
    (1080, 1080),
    (1080, 1350),
    (1080, 1920),
    (1200, 628),
}

# Blur: Laplacian-gradient variance below this → possibly blurry
_BLUR_THRESHOLD = 40.0
# Margin variance above this → content too close to edge
_MARGIN_VARIANCE_THRESHOLD = 1200.0


class QualityFinding(BaseModel):
    check: str
    severity: Literal["warning", "blocked"]
    detail: str
    checker_type: Literal["deterministic", "cv", "ai"] = "deterministic"


class QualityResult(BaseModel):
    result: str  # PASS | WARNING | BLOCKED
    findings: list[QualityFinding]


class QualityEngine:
    """
    Multi-stage image quality checker.

    Stage 1 — deterministic: format, size, dimensions, prompt.
    Stage 2 — CV (Pillow + numpy): blur, margins, brand color (if cv_enabled=True).
    Stage 3 — AI vision: opt-in only (ai_enabled=True), not implemented in Phase 4 MVP.
    """

    def __init__(self, *, cv_enabled: bool = True, ai_enabled: bool = False) -> None:
        self._cv = cv_enabled
        self._ai = ai_enabled

    # ── Public ─────────────────────────────────────────────────────

    def check(
        self,
        *,
        data: bytes | None = None,
        file_path: str = "",  # backward compat
        width: int | None = None,
        height: int | None = None,
        prompt_text: str | None = None,
        brand_colors: list[str] | None = None,
        extra_findings: list[QualityFinding] | None = None,
    ) -> QualityResult:
        """
        Run all applicable quality checks.

        Pass `data` (bytes) for Phase 4+ flow or `file_path` for legacy callers.
        `extra_findings` are pre-computed findings (e.g. duplicate hash) injected by CreativeService.
        """
        findings: list[QualityFinding] = list(extra_findings or [])

        # ── Resolve data ──────────────────────────────────────────
        if data is None and file_path:
            p = pathlib.Path(file_path)
            if not p.exists():
                findings.append(QualityFinding(
                    check="file_exists", severity="blocked",
                    detail="Image file not found at provided path.",
                ))
                return QualityResult(result=RESULT_BLOCKED, findings=findings)
            data = p.read_bytes()
            # Derive format from path if not provided
            suffix = p.suffix.lstrip(".").lower()
            if suffix not in VALID_FORMATS:
                findings.append(QualityFinding(
                    check="format", severity="blocked",
                    detail=f"Invalid format '{suffix}'. Allowed: {VALID_FORMATS}",
                ))

        if data is None:
            findings.append(QualityFinding(
                check="file_exists", severity="blocked",
                detail="No image data provided.",
            ))
            return QualityResult(result=RESULT_BLOCKED, findings=findings)

        # ── Stage 1: Deterministic ────────────────────────────────
        findings.extend(self._check_deterministic(data, width, height, prompt_text, file_path))

        # ── Stage 2: CV (Pillow) ──────────────────────────────────
        if self._cv:
            findings.extend(self._check_cv(data, brand_colors))

        # ── Stage 3: AI (opt-in, stub) ────────────────────────────
        # Phase 4 MVP: AI checks not implemented. Enable via QUALITY_AI_ENABLED=true
        # when anthropic_client integration is wired up.

        # ── Result ────────────────────────────────────────────────
        if any(f.severity == "blocked" for f in findings):
            result = RESULT_BLOCKED
        elif findings:
            result = RESULT_WARNING
        else:
            result = RESULT_PASS

        return QualityResult(result=result, findings=findings)

    # ── Stage 1: Deterministic ────────────────────────────────────

    def _check_deterministic(
        self,
        data: bytes,
        width: int | None,
        height: int | None,
        prompt_text: str | None,
        file_path: str,
    ) -> list[QualityFinding]:
        findings: list[QualityFinding] = []

        # File size
        size_mb = len(data) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            findings.append(QualityFinding(
                check="file_size", severity="blocked",
                detail=f"File is {size_mb:.1f} MB; max is {MAX_FILE_SIZE_MB} MB.",
            ))

        # Integrity / format via Pillow
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(data))
            img.verify()  # raises on corrupt file
            # Re-open after verify (verify closes the file)
            img = Image.open(io.BytesIO(data))
            detected_fmt = (img.format or "").lower()
            if detected_fmt not in VALID_FORMATS and detected_fmt not in {"", None}:
                findings.append(QualityFinding(
                    check="format", severity="blocked",
                    detail=f"Detected format '{detected_fmt}' is not in allowed set {VALID_FORMATS}.",
                ))
        except Exception as exc:
            findings.append(QualityFinding(
                check="file_corrupt", severity="blocked",
                detail=f"Image file is corrupt or unreadable: {exc}",
            ))
            return findings  # no point continuing

        # Dimensions
        if width and height and (width, height) not in VALID_DIMENSIONS:
            findings.append(QualityFinding(
                check="dimensions", severity="warning",
                detail=f"Dimensions {width}×{height} are non-standard. Recommended: {sorted(VALID_DIMENSIONS)}",
            ))

        # Prompt present
        if not prompt_text:
            findings.append(QualityFinding(
                check="prompt_present", severity="warning",
                detail="No prompt text associated with this creative.",
            ))

        return findings

    # ── Stage 2: CV (Pillow + numpy) ─────────────────────────────

    def _check_cv(
        self,
        data: bytes,
        brand_colors: list[str] | None,
    ) -> list[QualityFinding]:
        findings: list[QualityFinding] = []
        try:
            import numpy as np
            from PIL import Image

            img = Image.open(io.BytesIO(data)).convert("RGB")
            arr = np.array(img, dtype=float)

            # ── Blur detection ────────────────────────────────────
            gray = np.mean(arr, axis=2)
            gy, gx = np.gradient(gray)
            blur_var = float(np.var(np.sqrt(gx**2 + gy**2)))
            if blur_var < _BLUR_THRESHOLD:
                findings.append(QualityFinding(
                    check="image_quality_blur", severity="warning",
                    detail=f"Image appears blurry or low contrast (sharpness score: {blur_var:.1f} < {_BLUR_THRESHOLD}).",
                    checker_type="cv",
                ))

            # ── Margin safe area ──────────────────────────────────
            h, w, _ = arr.shape
            mh = max(1, int(h * 0.05))
            mw = max(1, int(w * 0.05))
            edge_pixels = np.concatenate([
                arr[:mh, :, :].reshape(-1, 3),
                arr[-mh:, :, :].reshape(-1, 3),
                arr[:, :mw, :].reshape(-1, 3),
                arr[:, -mw:, :].reshape(-1, 3),
            ])
            edge_var = float(np.var(edge_pixels))
            if edge_var > _MARGIN_VARIANCE_THRESHOLD:
                findings.append(QualityFinding(
                    check="margin_safe_area", severity="warning",
                    detail="Content appears too close to edges; text or product may be cut off in some placements.",
                    checker_type="cv",
                ))

            # ── Brand color presence ──────────────────────────────
            if brand_colors:
                found = _check_brand_color(arr, brand_colors)
                if not found:
                    findings.append(QualityFinding(
                        check="brand_color", severity="warning",
                        detail=f"None of the brand colors {brand_colors} were detected in the image.",
                        checker_type="cv",
                    ))

        except ImportError:
            pass  # numpy not available — skip CV checks silently
        except Exception:
            pass  # CV checks are best-effort; never block on their failure

        return findings


def _check_brand_color(
    arr,  # numpy float array H×W×3
    hex_colors: list[str],
    tolerance: int = 60,
) -> bool:
    import numpy as np

    for hc in hex_colors:
        hc = hc.lstrip("#")
        if len(hc) < 6:
            continue
        try:
            r, g, b = int(hc[0:2], 16), int(hc[2:4], 16), int(hc[4:6], 16)
        except ValueError:
            continue
        diffs = np.sqrt(((arr - [r, g, b]) ** 2).sum(axis=2))
        if bool((diffs < tolerance).any()):
            return True
    return False
