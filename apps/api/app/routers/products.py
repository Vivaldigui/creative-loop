from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_org, require_roles
from app.models.product import Product
from app.models.user import User

router = APIRouter()


class ProductCreate(BaseModel):
    name: str
    description: str | None = None
    category: str | None = None


class ProductOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    category: str | None
    status: str
    is_fictitious: bool

    model_config = {"from_attributes": True}


@router.get("")
async def list_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
) -> list[ProductOut]:
    result = await db.execute(
        select(Product).where(Product.organization_id == org_id, Product.status == "active")
    )
    return [ProductOut.model_validate(p) for p in result.scalars().all()]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    _user: Annotated[User, Depends(require_roles("owner", "admin"))],
) -> ProductOut:
    product = Product(
        organization_id=org_id,
        name=body.name,
        description=body.description,
        category=body.category,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return ProductOut.model_validate(product)


@router.get("/{product_id}")
async def get_product(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
) -> ProductOut:
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.organization_id == org_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductOut.model_validate(product)
