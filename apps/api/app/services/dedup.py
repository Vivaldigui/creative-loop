"""
Deduplication helpers — sha256 exact-match and pHash near-duplicate detection.

These run against the DB to check if an image already exists in the org.
"""
from __future__ import annotations

import hashlib
import io
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_phash(data: bytes) -> str:
    """Return a hex perceptual hash string using imagehash.phash."""
    import imagehash
    from PIL import Image

    img = Image.open(io.BytesIO(data)).convert("RGB")
    return str(imagehash.phash(img))


def phash_distance(h1: str, h2: str) -> int:
    """Return Hamming distance between two pHash hex strings."""
    import imagehash

    return imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2)


async def find_duplicate_hash(
    db: AsyncSession,
    org_id: uuid.UUID,
    file_hash: str,
) -> uuid.UUID | None:
    """Return creative_asset.id if an identical file hash already exists in the org."""
    from app.models.creative_asset import CreativeAsset

    result = await db.execute(
        select(CreativeAsset.id).where(
            CreativeAsset.organization_id == org_id,
            CreativeAsset.file_hash == file_hash,
            CreativeAsset.role == "original",
        ).limit(1)
    )
    row = result.scalar_one_or_none()
    return row


async def find_similar_phash(
    db: AsyncSession,
    org_id: uuid.UUID,
    phash_str: str,
    threshold: int = 6,
    exclude_id: uuid.UUID | None = None,
) -> uuid.UUID | None:
    """Return creative.id if a similar pHash exists in the org (Hamming distance ≤ threshold)."""
    from app.models.creative import GeneratedCreative

    result = await db.execute(
        select(GeneratedCreative.id, GeneratedCreative.phash).where(
            GeneratedCreative.organization_id == org_id,
            GeneratedCreative.phash.isnot(None),
            GeneratedCreative.status.not_in(["failed"]),
        ).limit(300)
    )
    rows = result.all()

    for row in rows:
        if exclude_id and row.id == exclude_id:
            continue
        try:
            dist = phash_distance(phash_str, row.phash)
            if 0 < dist <= threshold:
                logger.debug("similar_phash_found", distance=dist, creative_id=str(row.id))
                return row.id
        except Exception:
            continue
    return None
