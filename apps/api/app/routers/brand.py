from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_org, require_roles
from app.models.product import BrandProfile
from app.models.user import User

router = APIRouter()


class BrandProfileCreate(BaseModel):
    product_id: uuid.UUID
    name: str
    primary_color: str | None = None
    secondary_color: str | None = None
    font_family: str | None = None
    tone_of_voice: str | None = None
    logo_guidelines: str | None = None
    prohibited_elements: str | None = None


class BrandProfileOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    name: str
    primary_color: str | None
    secondary_color: str | None
    font_family: str | None
    tone_of_voice: str | None
    status: str

    model_config = {"from_attributes": True}


@router.get("")
async def list_brand_profiles(
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
) -> list[BrandProfileOut]:
    result = await db.execute(
        select(BrandProfile).where(BrandProfile.organization_id == org_id)
    )
    return [BrandProfileOut.model_validate(b) for b in result.scalars().all()]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_brand_profile(
    body: BrandProfileCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    _user: Annotated[User, Depends(require_roles("owner", "admin"))],
) -> BrandProfileOut:
    brand = BrandProfile(
        organization_id=org_id,
        product_id=body.product_id,
        name=body.name,
        primary_color=body.primary_color,
        secondary_color=body.secondary_color,
        font_family=body.font_family,
        tone_of_voice=body.tone_of_voice,
        logo_guidelines=body.logo_guidelines,
        prohibited_elements=body.prohibited_elements,
    )
    db.add(brand)
    await db.commit()
    await db.refresh(brand)
    return BrandProfileOut.model_validate(brand)
