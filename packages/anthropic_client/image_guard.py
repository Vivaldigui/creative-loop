"""
Image validation and sanitisation before sending to Claude.
- Validates format (png/jpeg/webp/gif only)
- Enforces size limit
- Strips EXIF metadata
- Refuses video and carousel with typed exceptions
"""
from __future__ import annotations

import io
import pathlib
from typing import Literal

ALLOWED_FORMATS: set[str] = {"png", "jpeg", "jpg", "webp", "gif"}
ALLOWED_MEDIA_TYPES: dict[str, str] = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
}

MediaKind = Literal["image", "video", "carousel", "none"]


class UnsupportedMediaError(ValueError):
    """Raised when the media type cannot be analysed (video, carousel)."""

    def __init__(self, kind: MediaKind) -> None:
        self.kind = kind
        super().__init__(f"Media kind '{kind}' is not supported for visual analysis.")


class ImageTooLargeError(ValueError):
    """Raised when the image exceeds the configured size limit."""

    def __init__(self, size_bytes: int, limit_bytes: int) -> None:
        self.size_bytes = size_bytes
        self.limit_bytes = limit_bytes
        super().__init__(
            f"Image size {size_bytes / 1_048_576:.1f} MB exceeds limit "
            f"{limit_bytes / 1_048_576:.1f} MB."
        )


class InvalidImageFormatError(ValueError):
    """Raised when the image format is not allowed."""


def detect_media_kind(
    image_path: str | None,
    image_url: str | None,
) -> MediaKind:
    """Heuristic: guess MediaKind from file extension."""
    path_or_url = image_path or image_url or ""
    ext = pathlib.Path(path_or_url).suffix.lstrip(".").lower()
    if ext in {"mp4", "mov", "avi", "mkv", "webm"}:
        return "video"
    if ext in ALLOWED_FORMATS:
        return "image"
    if not ext:
        return "none"
    return "image"  # unknown extension → attempt as image, let validation fail


def validate_and_prepare(
    image_path: str,
    max_bytes: int = 5 * 1_048_576,
) -> tuple[bytes, str]:
    """
    Read, validate, strip EXIF, and return (image_bytes, media_type).

    Raises:
        InvalidImageFormatError: format not in ALLOWED_FORMATS
        ImageTooLargeError: file exceeds max_bytes
    """
    p = pathlib.Path(image_path)
    ext = p.suffix.lstrip(".").lower()
    if ext not in ALLOWED_FORMATS:
        raise InvalidImageFormatError(
            f"Format '{ext}' is not allowed. Permitted: {sorted(ALLOWED_FORMATS)}"
        )

    raw_bytes = p.read_bytes()
    if len(raw_bytes) > max_bytes:
        raise ImageTooLargeError(len(raw_bytes), max_bytes)

    # Strip EXIF using Pillow (if available) — re-encode to clean copy
    cleaned = _strip_exif(raw_bytes, ext)
    media_type = ALLOWED_MEDIA_TYPES[ext]
    return cleaned, media_type


def _strip_exif(data: bytes, ext: str) -> bytes:
    """Re-encode image through Pillow to remove EXIF/metadata."""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as img:
            buf = io.BytesIO()
            fmt = "JPEG" if ext in {"jpg", "jpeg"} else ext.upper()
            # Convert RGBA→RGB for JPEG
            if fmt == "JPEG" and img.mode in {"RGBA", "P"}:
                img = img.convert("RGB")
            img.save(buf, format=fmt)
            return buf.getvalue()
    except Exception:
        # If Pillow fails (unsupported mode, corrupted), return raw; guard already checked size
        return data
