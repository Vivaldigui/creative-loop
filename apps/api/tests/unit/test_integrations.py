from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.routers import integrations


class _HealthyClient:
    async def health_check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_openai_test_passes_configured_credentials(monkeypatch):
    captured = {}
    settings = SimpleNamespace(
        openai_api_key="sk-test-openai",
        image_provider="openai",
        openai_image_model="gpt-image-2",
        openai_timeout_s=45.0,
        openai_max_retries=2,
    )

    def fake_factory(**kwargs):
        captured.update(kwargs)
        return _HealthyClient()

    monkeypatch.setattr(integrations, "get_settings", lambda: settings)
    monkeypatch.setattr(
        "packages.openai_image_client.factory.get_image_client",
        fake_factory,
    )

    result = await integrations.test_integration("openai", object())

    assert result == {"provider": "openai", "status": "ok"}
    assert captured == {
        "provider": "openai",
        "api_key": "sk-test-openai",
        "model": "gpt-image-2",
        "timeout_s": 45.0,
        "max_retries": 2,
    }


@pytest.mark.asyncio
async def test_anthropic_test_passes_configured_credentials(monkeypatch):
    captured = {}
    settings = SimpleNamespace(
        anthropic_api_key="sk-test-anthropic",
        anthropic_provider="real",
        anthropic_model="claude-sonnet-4-6",
        anthropic_max_image_mb=5.0,
        anthropic_price_input_per_mtok=None,
        anthropic_price_output_per_mtok=None,
    )

    def fake_factory(**kwargs):
        captured.update(kwargs)
        return _HealthyClient()

    monkeypatch.setattr(integrations, "get_settings", lambda: settings)
    monkeypatch.setattr(
        "packages.anthropic_client.factory.get_anthropic_client",
        fake_factory,
    )

    result = await integrations.test_integration("anthropic", object())

    assert result == {"provider": "anthropic", "status": "ok"}
    assert captured == {
        "provider": "real",
        "api_key": "sk-test-anthropic",
        "model": "claude-sonnet-4-6",
        "max_image_bytes": 5 * 1_048_576,
        "price_input_per_mtok": None,
        "price_output_per_mtok": None,
    }
