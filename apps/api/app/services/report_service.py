"""
ReportService — generates daily and weekly reports.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.evaluation import ExperimentEvaluation
from app.models.experiment import Experiment
from app.models.learning import Learning
from app.models.publish import PublishedAd
from app.models.suggestion import ExperimentSuggestion
from app.models.variant_metric import VariantPerformanceSnapshot
from app.schemas.report import AlertItem, DailyReportOut, WeeklyReportOut

logger = structlog.get_logger()


class ReportService:

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def daily(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        report_date: date | None = None,
    ) -> DailyReportOut:
        if not report_date:
            report_date = date.today()

        date_str = report_date.isoformat()
        prev_str = (report_date - timedelta(days=1)).isoformat()
        alerts: list[AlertItem] = []

        # Total spend from variant snapshots for this date
        snap_result = await db.execute(
            select(VariantPerformanceSnapshot).where(
                VariantPerformanceSnapshot.organization_id == org_id,
                VariantPerformanceSnapshot.date_start >= prev_str,
                VariantPerformanceSnapshot.date_stop <= date_str,
            )
        )
        snaps = snap_result.scalars().all()
        total_spend = sum(s.spend or 0.0 for s in snaps) or None

        # Anomalous spend detection
        median_spend = _rolling_median_spend(snaps)
        if median_spend and total_spend and total_spend > self._settings.anomalous_spend_multiplier * median_spend:
            alerts.append(AlertItem(
                level="critical",
                code="anomalous_spend",
                message=f"Daily spend {total_spend:.2f} is {total_spend / median_spend:.1f}× above rolling median ({median_spend:.2f}).",
            ))

        # Ads without conversions
        ads_no_conv = []
        for s in snaps:
            if (s.purchases or 0) == 0 and (s.leads or 0) == 0 and (s.spend or 0) > 10:
                ads_no_conv.append({
                    "variant_id": str(s.variant_id),
                    "spend": s.spend,
                    "date_start": s.date_start,
                })

        # Rejected published ads
        pad_result = await db.execute(
            select(PublishedAd).where(
                PublishedAd.organization_id == org_id,
                PublishedAd.effective_status == "DISAPPROVED",
            )
        )
        rejected_pads = [{"id": str(p.id), "meta_ad_id": p.meta_ad_id} for p in pad_result.scalars().all()]
        if rejected_pads:
            alerts.append(AlertItem(
                level="warning",
                code="rejected_ads",
                message=f"{len(rejected_pads)} ad(s) disapproved by Meta.",
            ))

        # Experiments with issues
        exp_result = await db.execute(
            select(Experiment).where(
                Experiment.organization_id == org_id,
                Experiment.status.in_(["running", "evaluating"]),
            )
        )
        experiments = exp_result.scalars().all()
        exp_issues = []
        for exp in experiments:
            eval_result = await db.execute(
                select(ExperimentEvaluation)
                .where(
                    ExperimentEvaluation.experiment_id == exp.id,
                    ExperimentEvaluation.organization_id == org_id,
                )
                .order_by(ExperimentEvaluation.evaluated_at.desc())
                .limit(1)
            )
            ev = eval_result.scalar_one_or_none()
            state = ev.evaluation_state if ev else "no_evaluation"
            if state in ("insufficient_data", "stopped_for_safety"):
                exp_issues.append({"id": str(exp.id), "name": exp.name, "state": state})
                alerts.append(AlertItem(
                    level="warning",
                    code=f"experiment_{state}",
                    message=f"Experiment '{exp.name}' is in state '{state}'.",
                    entity_id=str(exp.id),
                    entity_type="experiment",
                ))

        running = sum(1 for e in experiments if e.status == "running")
        evaluating = sum(1 for e in experiments if e.status == "evaluating")

        return DailyReportOut(
            report_date=report_date,
            generated_at=datetime.now(UTC),
            period_start=prev_str,
            period_end=date_str,
            total_spend=round(total_spend, 2) if total_spend else None,
            currency=self._settings.default_currency,
            alerts=alerts,
            ads_without_conversions=ads_no_conv,
            rejected_ads=rejected_pads,
            experiments_with_issues=exp_issues,
            running_experiments=running,
            evaluating_experiments=evaluating,
        )

    async def weekly(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        week_start: date | None = None,
    ) -> WeeklyReportOut:
        if not week_start:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        iso_week = f"{week_start.year}-W{week_start.isocalendar()[1]:02d}"

        # Completed experiments this week
        comp_result = await db.execute(
            select(Experiment).where(
                Experiment.organization_id == org_id,
                Experiment.status.in_(["completed", "stopped"]),
                Experiment.ended_at >= datetime.combine(week_start, datetime.min.time()),
                Experiment.ended_at <= datetime.combine(week_end, datetime.max.time()),
            )
        )
        completed_exps = comp_result.scalars().all()
        completed_list = []
        for exp in completed_exps:
            eval_result = await db.execute(
                select(ExperimentEvaluation)
                .where(ExperimentEvaluation.experiment_id == exp.id, ExperimentEvaluation.organization_id == org_id)
                .order_by(ExperimentEvaluation.evaluated_at.desc()).limit(1)
            )
            ev = eval_result.scalar_one_or_none()
            completed_list.append({
                "id": str(exp.id),
                "name": exp.name,
                "mode": exp.mode,
                "stop_reason": exp.stop_reason,
                "evaluation_state": ev.evaluation_state if ev else None,
                "confidence": ev.confidence if ev else None,
                "limitations_count": len(ev.limitations or []) if ev else 0,
            })

        # Promising and rejected patterns
        promising = [e for e in completed_list if (e.get("evaluation_state") or "") in ("winner_candidate", "promising")]
        rejected = [e for e in completed_list if (e.get("evaluation_state") or "") == "underperforming"]

        # New learnings this week
        learn_result = await db.execute(
            select(Learning).where(
                Learning.organization_id == org_id,
                Learning.created_at >= datetime.combine(week_start, datetime.min.time()),
            )
        )
        new_learnings = [
            {"id": str(lr.id), "pattern": lr.observed_pattern[:120], "status": lr.status, "confidence": lr.confidence}
            for lr in learn_result.scalars().all()
        ]

        # Suggestions
        sug_result = await db.execute(
            select(ExperimentSuggestion).where(
                ExperimentSuggestion.organization_id == org_id,
                ExperimentSuggestion.created_at >= datetime.combine(week_start, datetime.min.time()),
            )
        )
        suggestions = [
            {"id": str(s.id), "hypothesis": (s.hypothesis or "")[:120], "status": s.status, "diversity_score": s.diversity_score}
            for s in sug_result.scalars().all()
        ]

        # Weekly spend
        snap_result = await db.execute(
            select(VariantPerformanceSnapshot).where(
                VariantPerformanceSnapshot.organization_id == org_id,
                VariantPerformanceSnapshot.date_start >= week_start.isoformat(),
                VariantPerformanceSnapshot.date_stop <= week_end.isoformat(),
            )
        )
        total_spend = sum(s.spend or 0.0 for s in snap_result.scalars().all()) or None

        return WeeklyReportOut(
            report_week=iso_week,
            generated_at=datetime.now(UTC),
            period_start=week_start.isoformat(),
            period_end=week_end.isoformat(),
            completed_experiments=completed_list,
            promising_patterns=promising,
            rejected_patterns=rejected,
            new_learnings=new_learnings,
            suggestions=suggestions,
            total_spend=round(total_spend, 2) if total_spend else None,
            currency=self._settings.default_currency,
        )


def _rolling_median_spend(snaps: list[VariantPerformanceSnapshot]) -> float | None:
    values = sorted(s.spend for s in snaps if s.spend is not None)
    if not values:
        return None
    mid = len(values) // 2
    if len(values) % 2 == 0:
        return (values[mid - 1] + values[mid]) / 2.0
    return values[mid]
