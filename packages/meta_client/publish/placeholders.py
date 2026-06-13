"""
Named placeholder constants for Meta configuration fields not yet filled.

These are surfaced in payloads and validation checks so the user knows exactly
which configuration is missing before Phase 6 (real publish).
They are NEVER invented IDs — they are clearly marked strings that will cause
Meta API calls to fail if sent, acting as a safety net.
"""

PENDING_META_AD_ACCOUNT_ID = "PENDING_META_AD_ACCOUNT_ID"
PENDING_META_PAGE_ID = "PENDING_META_PAGE_ID"
PENDING_META_INSTAGRAM_ACTOR_ID = "PENDING_META_INSTAGRAM_ACTOR_ID"
PENDING_META_PIXEL_ID = "PENDING_META_PIXEL_ID"

# The image_hash Meta would return after upload — simulated only
PENDING_META_IMAGE_HASH = "PENDING_META_IMAGE_HASH_AFTER_UPLOAD"

_PREENCHER_PREFIX = "PREENCHER_"
_PENDING_PREFIX = "PENDING_"


def is_placeholder(value: str | None) -> bool:
    """Return True if the value is an unfilled placeholder."""
    if not value:
        return True
    return value.startswith(_PREENCHER_PREFIX) or value.startswith(_PENDING_PREFIX)


def resolve(configured: str, fallback: str) -> str:
    """Return configured value if filled, otherwise the named fallback placeholder."""
    if is_placeholder(configured):
        return fallback
    return configured
