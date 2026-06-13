from __future__ import annotations

import os
import uuid

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".webp"})


def make_key(org_id: str | uuid.UUID, ext: str = ".png") -> str:
    """Generate unpredictable storage key scoped to org (never guessable)."""
    clean_ext = ext.lower() if ext.lower() in ALLOWED_EXTENSIONS else ".bin"
    return f"{org_id}/{uuid.uuid4().hex}{clean_ext}"


def validate_key(org_id: str | uuid.UUID, key: str) -> bool:
    """Return True only if key is safe and belongs to org."""
    prefix = str(org_id)
    if not key or not key.strip():
        return False
    # No path traversal
    if ".." in key:
        return False
    # Must not be absolute
    if key.startswith("/") or key.startswith("\\"):
        return False
    # No null bytes
    if "\x00" in key:
        return False
    # Must be prefixed with org_id
    if not key.startswith(f"{prefix}/"):
        return False
    # Tail must not escape the org dir
    tail = key[len(prefix) + 1:]
    return not (os.path.isabs(tail) or ".." in tail)


def ext_for_mime(mime: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }.get(mime, ".png")
