from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class StoredObject(BaseModel):
    key: str
    size: int
    content_type: str
    hash: str  # sha256 hex
    backend: str  # local | s3


@runtime_checkable
class StorageBackend(Protocol):
    async def put(self, org_id: str, key: str, data: bytes, content_type: str) -> StoredObject: ...
    async def get(self, org_id: str, key: str) -> bytes: ...
    def signed_url(self, org_id: str, key: str, ttl: int = 600) -> str: ...
    async def delete(self, org_id: str, key: str) -> None: ...
    async def exists(self, org_id: str, key: str) -> bool: ...
    def local_path(self, org_id: str, key: str) -> str | None: ...
