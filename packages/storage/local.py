from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path

import structlog

from .interface import StoredObject
from .paths import validate_key

logger = structlog.get_logger()


class LocalStorage:
    """Development-grade local filesystem storage.

    Files live at  <base_dir>/<org_id>/<uuid>.ext
    Signed URLs are HMAC-authenticated tokens served by GET /assets/{token}.
    """

    def __init__(self, base_dir: str, secret_key: str) -> None:
        self._base = Path(base_dir).resolve()
        self._secret = secret_key.encode()

    # ── Public API ────────────────────────────────────────────────

    async def put(self, org_id: str, key: str, data: bytes, content_type: str) -> StoredObject:
        if not validate_key(org_id, key):
            raise ValueError(f"Unsafe storage key rejected: {key!r}")
        path = self._base / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        h = hashlib.sha256(data).hexdigest()
        logger.debug("storage_put", backend="local", key=key, size=len(data))
        return StoredObject(key=key, size=len(data), content_type=content_type, hash=h, backend="local")

    async def get(self, org_id: str, key: str) -> bytes:
        if not validate_key(org_id, key):
            raise ValueError(f"Unsafe storage key rejected: {key!r}")
        return (self._base / key).read_bytes()

    def signed_url(self, org_id: str, key: str, ttl: int = 600) -> str:
        """Return a short-lived URL served by GET /assets/{token}."""
        exp = int(time.time()) + ttl
        msg = f"{org_id}:{key}:{exp}"
        sig = hmac.new(self._secret, msg.encode(), hashlib.sha256).hexdigest()
        token = base64.urlsafe_b64encode(
            json.dumps({"o": org_id, "k": key, "e": exp, "s": sig}).encode()
        ).decode().rstrip("=")
        return f"/assets/{token}"

    def verify_token(self, token: str) -> dict[str, str]:
        """Decode and validate a signed token. Raises ValueError on any problem."""
        try:
            padded = token + "=" * (-len(token) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        except Exception as exc:
            raise ValueError("Invalid token encoding") from exc

        org_id = payload.get("o")
        key = payload.get("k")
        exp = payload.get("e")
        sig = payload.get("s")

        if not all([org_id, key, exp, sig]):
            raise ValueError("Missing required token fields")
        if int(exp) < int(time.time()):
            raise ValueError("Token has expired")

        msg = f"{org_id}:{key}:{exp}"
        expected = hmac.new(self._secret, msg.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise ValueError("Token signature mismatch")

        return {"org_id": str(org_id), "key": str(key)}

    async def delete(self, org_id: str, key: str) -> None:
        if not validate_key(org_id, key):
            raise ValueError(f"Unsafe storage key rejected: {key!r}")
        p = self._base / key
        if p.exists():
            p.unlink()
            logger.debug("storage_delete", backend="local", key=key)

    async def exists(self, org_id: str, key: str) -> bool:
        if not validate_key(org_id, key):
            return False
        return (self._base / key).exists()

    def local_path(self, org_id: str, key: str) -> str | None:
        """Return the absolute filesystem path (local backend only)."""
        if not validate_key(org_id, key):
            return None
        return str(self._base / key)
