"""
Reports router — daily and weekly operational reports.
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_org, get_current_user
from app.models.user import User
from app.schemas.report import DailyReportOut, WeeklyReportOut
from app.services.report_service import ReportService

router = APIRouter()


def _svc():
    return ReportService(get_settings())


@router.get("/daily", response_model=DailyReportOut)
async def daily_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    report_date: date | None = Query(None, description="ISO date (YYYY-MM-DD), defaults to today"),
):
    return await _svc().daily(db, org_id, report_date=report_date)


@router.get("/weekly", response_model=WeeklyReportOut)
async def weekly_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    week_start: date | None = Query(None, description="ISO date of Monday of the week, defaults to current week"),
):
    return await _svc().weekly(db, org_id, week_start=week_start)
