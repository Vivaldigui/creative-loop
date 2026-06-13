from __future__ import annotations

from .interface import AnthropicClientProtocol
from .mock import MockAnthropicClient


def get_anthropic_client(
    provider: str = "mock",
    api_key: str | None = None,
    model: str = "claude-sonnet-4-6",
    max_image_bytes: int = 5 * 1_048_576,
    price_input_per_mtok: float | None = None,
    price_output_per_mtok: float | None = None,
) -> AnthropicClientProtocol:
    if provider == "real":
        from .real import RealAnthropicClient
        return RealAnthropicClient(
            api_key=api_key or "",
            model=model,
            max_image_bytes=max_image_bytes,
            price_input_per_mtok=price_input_per_mtok,
            price_output_per_mtok=price_output_per_mtok,
        )
    return MockAnthropicClient()
