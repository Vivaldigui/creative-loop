from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field


class ImageRequest(BaseModel):
    prompt: str
    width: int = 1080
    height: int = 1080
    quality: Literal["standard", "hd"] = "standard"
    n: int = Field(default=1, ge=1, le=4)
    # Internal storage key of a brand asset to use as edit reference (not an external URL)
    reference_asset_key: str | None = None
    mode: Literal["generate", "edit"] = "generate"


class ImageBytesResult(BaseModel):
    """Raw bytes returned by the provider — storage is handled by CreativeService."""

    images: list[bytes]
    mime_type: str = "image/png"
    provider: str
    model_used: str | None = None
    estimated_cost_usd: float | None = None
    parameters: dict | None = None
    moderation_flagged: bool = False

    model_config = {"arbitrary_types_allowed": True}


# Kept for backward compatibility with Phase-1 callers that used ImageResult
class ImageResult(BaseModel):
    file_path: str
    file_hash: str
    width: int
    height: int
    file_size_bytes: int
    mime_type: str = "image/png"
    provider: str
    model_used: str | None = None
    estimated_cost_usd: float | None = None
    parameters: dict | None = None


class ImageClientProtocol(Protocol):
    async def generate(self, request: ImageRequest) -> ImageBytesResult: ...
    async def edit(self, request: ImageRequest) -> ImageBytesResult: ...
    async def health_check(self) -> bool: ...
