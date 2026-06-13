from __future__ import annotations

from .interface import ImageClientProtocol
from .mock import MockImageClient


def get_image_client(
    provider: str = "mock",
    *,
    api_key: str = "",
    model: str = "gpt-image-2",
    timeout_s: float = 90.0,
    max_retries: int = 3,
    # Deprecated — kept for Phase-1 callers
    storage_dir: str = "./storage",  # noqa: ARG001
) -> ImageClientProtocol:
    if provider == "openai":
        from .real import OpenAIImageClient
        return OpenAIImageClient(
            api_key=api_key,
            model=model,
            timeout_s=timeout_s,
            max_retries=max_retries,
        )
    return MockImageClient()
