"""Integration tests for authentication."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_login_invalid_credentials(seeded_client):
    client, *_ = seeded_client
    resp = await client.post("/auth/login", json={"email": "owner@orga.example", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_valid(seeded_client):
    client, user, *_ = seeded_client
    resp = await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "owner@orga.example"
    assert "access_token" in client.cookies


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user(seeded_client):
    client, user, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})
    resp = await client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "owner@orga.example"


@pytest.mark.asyncio
async def test_logout_clears_cookie(seeded_client):
    client, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})
    resp = await client.post("/auth/logout")
    assert resp.status_code == 200
    resp2 = await client.get("/auth/me")
    assert resp2.status_code == 401
