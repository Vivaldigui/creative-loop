"""Pydantic schemas for daily and weekly reports."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class AlertItem(BaseModel):
    level: str  # warning | critical
    code: str
    message: str
    entity_id: str | None = None
    entity_type: str | None = None


class DailyReportOut(BaseModel):
    report_date: date
    generated_at: datetime
    period_start: str
    period_end: str
    # Spend summary
    total_spend: float | None
    currency: str
    # Alerts
    alerts: list[AlertItem]
    # Ads without conversions
    ads_without_conversions: list[dict[str, Any]]
    # Rejected ads
    rejected_ads: list[dict[str, Any]]
    # Experiments with issues
    experiments_with_issues: list[dict[str, Any]]
    # Running experiments summary
    running_experiments: int
    evaluating_experiments: int
    is_fictitious: bool = False


class WeeklyReportOut(BaseModel):
    report_week: str  # ISO week, e.g. "2025-W24"
    generated_at: datetime
    period_start: str
    period_end: str
    # Completed experiments
    completed_experiments: list[dict[str, Any]]
    # Promising patterns
    promising_patterns: list[dict[str, Any]]
    # Rejected patterns (underperforming)
    rejected_patterns: list[dict[str, Any]]
    # New learnings this week
    new_learnings: list[dict[str, Any]]
    # Suggestions for next round
    suggestions: list[dict[str, Any]]
    # Stats
    total_spend: float | None
    currency: str
    is_fictitious: bool = False
