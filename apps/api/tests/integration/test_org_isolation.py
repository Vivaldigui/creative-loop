"""Test that org A cannot access org B data."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_org_isolation_products(seeded_client, db_session):
    client, user_a, org_a, user_b, org_b = seeded_client
    from app.models.product import Product

    # Create a product in org B
    prod_b = Product(organization_id=org_b.id, name="Org B Product", status="active")
    db_session.add(prod_b)
    await db_session.commit()

    # Login as org A
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    # Org A should NOT see org B's product
    resp = await client.get("/products")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "Org B Product" not in names
