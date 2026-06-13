"""Unit tests for MockImageClient — zero cost, valid PNG output."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from packages.openai_image_client.interface import ImageRequest
from packages.openai_image_client.mock import MockImageClient


@pytest.mark.asyncio
async def test_generate_returns_bytes():
    client = MockImageClient()
    req = ImageRequest(prompt="Test prompt", width=256, height=256, n=1)
    result = await client.generate(req)
    assert len(result.images) == 1
    assert isinstance(result.images[0], bytes)
    assert len(result.images[0]) > 0


@pytest.mark.asyncio
async def test_generate_n_variations():
    client = MockImageClient()
    req = ImageRequest(prompt="Test", width=128, height=128, n=3)
    result = await client.generate(req)
    assert len(result.images) == 3


@pytest.mark.asyncio
async def test_generate_produces_valid_png():
    client = MockImageClient()
    req = ImageRequest(prompt="A nice ad", width=200, height=200, n=1)
    result = await client.generate(req)
    img = Image.open(io.BytesIO(result.images[0]))
    assert img.format == "PNG"


@pytest.mark.asyncio
async def test_generate_correct_dimensions():
    client = MockImageClient()
    req = ImageRequest(prompt="Ad", width=320, height=180, n=1)
    result = await client.generate(req)
    img = Image.open(io.BytesIO(result.images[0]))
    assert img.size == (320, 180)


@pytest.mark.asyncio
async def test_generate_zero_cost():
    client = MockImageClient()
    req = ImageRequest(prompt="Ad", width=128, height=128, n=1)
    result = await client.generate(req)
    assert result.estimated_cost_usd == 0.0


@pytest.mark.asyncio
async def test_generate_provider_name_is_mock():
    client = MockImageClient()
    req = ImageRequest(prompt="Ad", width=128, height=128, n=1)
    result = await client.generate(req)
    assert result.provider == "mock"


@pytest.mark.asyncio
async def test_generate_not_moderation_flagged():
    client = MockImageClient()
    req = ImageRequest(prompt="Ad", width=128, height=128, n=1)
    result = await client.generate(req)
    assert result.moderation_flagged is False


@pytest.mark.asyncio
async def test_health_check_true():
    assert await MockImageClient().health_check() is True


@pytest.mark.asyncio
async def test_edit_returns_bytes():
    client = MockImageClient()
    req = ImageRequest(prompt="Edit test", width=64, height=64, mode="edit")
    result = await client.edit(req)
    assert len(result.images) == 1


@pytest.mark.asyncio
async def test_parameters_recorded():
    client = MockImageClient()
    req = ImageRequest(prompt="Param test", width=64, height=64, n=2)
    result = await client.generate(req)
    assert result.parameters is not None
    assert result.parameters.get("n") == 2
