from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import distinct, func, or_
from sqlalchemy.orm import Session

from app.domain.models import Activity, ActualProgressLedger, ExecutionEvent, Project
from app.schemas.institutional_memory import (
    DurationMetricDTO,
    DurationSummaryDTO,
    EvidenceReferenceDTO,
    HistoricalLedgerEntryDTO,
    HistoricalLedgerPageDTO,
    HistoricalSummaryDTO,
    PlanningBenchmarkDTO,
    ProductivityMetricDTO,
)

logger = logging.getLogger("historical_analytics_service")

MIN_BENCHMARK_SAMPLE_SIZE = 3
MIN_PERCENTILE_SAMPLE_SIZE = 5


class HistoricalAnalyticsService:
    @classmethod
    def get_ledger_entries(
        cls,
        db: Session,
        project_id: str,
        activity_code: Optional[str] = None,
        discipline: Optional[str] = None,
        contractor: Optional[str] = None,
        location: Optional[str] = None,
        unit: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> HistoricalLedgerPageDTO:
        """
        Retrieves paginated, joined historical execution progress records from PostgreSQL.
        Ordered by reporting_date DESC, created_at DESC.
        """
        query = (
            db.query(ActualProgressLedger, Activity, ExecutionEvent, Project)
            .join(Activity, ActualProgressLedger.activity_id == Activity.id)
            .join(ExecutionEvent, ActualProgressLedger.execution_event_id == ExecutionEvent.id)
            .join(Project, ActualProgressLedger.project_id == Project.id)
            .filter(ActualProgressLedger.project_id == project_id)
        )

        if activity_code:
            query = query.filter(Activity.activity_code.ilike(f"%{activity_code.strip()}%"))
        if discipline:
            query = query.filter(
                or_(
                    ExecutionEvent.discipline.ilike(f"%{discipline.strip()}%"),
                    Activity.discipline.ilike(f"%{discipline.strip()}%"),
                )
            )
        if contractor:
            query = query.filter(
                or_(
                    ExecutionEvent.contractor.ilike(f"%{contractor.strip()}%"),
                    Activity.contractor_name.ilike(f"%{contractor.strip()}%"),
                )
            )
        if location:
            query = query.filter(
                or_(
                    ExecutionEvent.location.ilike(f"%{location.strip()}%"),
                    Activity.location_code.ilike(f"%{location.strip()}%"),
                )
            )
        if unit:
            query = query.filter(
                or_(
                    ActualProgressLedger.unit_of_measure.ilike(unit.strip()),
                    Activity.quantity_unit.ilike(unit.strip()),
                )
            )
        if from_date:
            query = query.filter(ActualProgressLedger.reporting_date >= from_date)
        if to_date:
            query = query.filter(ActualProgressLedger.reporting_date <= to_date)
        if source_type:
            query = query.filter(ExecutionEvent.source_type == source_type.strip().upper())
        if status:
            query = query.filter(ExecutionEvent.status == status.strip().upper())

        total = query.count()
        offset = max(0, (page - 1) * page_size)
        rows = (
            query.order_by(
                ActualProgressLedger.reporting_date.desc(),
                ActualProgressLedger.created_at.desc(),
            )
            .offset(offset)
            .limit(page_size)
            .all()
        )

        items: List[HistoricalLedgerEntryDTO] = []
        for ledger, act, ev, proj in rows:
            items.append(
                HistoricalLedgerEntryDTO(
                    ledger_id=ledger.id,
                    execution_event_id=ev.id,
                    project_id=proj.id,
                    project_code=proj.project_code,
                    activity_id=act.id,
                    activity_code=act.activity_code,
                    activity_name=act.name,
                    reporting_date=ledger.reporting_date.strftime("%Y-%m-%d %H:%M:%S")
                    if ledger.reporting_date
                    else "",
                    installed_quantity=ledger.installed_quantity,
                    unit_of_measure=ledger.unit_of_measure or act.quantity_unit,
                    incremental_percent=ledger.incremental_percent,
                    cumulative_percent=ledger.cumulative_percent,
                    status_reported=ev.status_reported,
                    source_type=ev.source_type,
                    discipline=ev.discipline or act.discipline,
                    contractor=ev.contractor or act.contractor_name,
                    location=ev.location or act.location_code,
                    source_document_name=ev.source_document_name,
                    artifact_id=ev.artifact_id,
                    created_at=ledger.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    if ledger.created_at
                    else "",
                )
            )

        total_pages = max(1, math.ceil(total / page_size))
        return HistoricalLedgerPageDTO(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @classmethod
    def calculate_productivity(
        cls,
        db: Session,
        project_id: str,
        discipline: Optional[str] = None,
        contractor: Optional[str] = None,
        activity_code: Optional[str] = None,
        unit: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[ProductivityMetricDTO]:
        """
        Calculates deterministic observed production rate:
        rate = SUM(installed_quantity) / COUNT(DISTINCT reporting_date::date)
        Strictly groups by compatible unit_of_measure. Incompatible units are never mixed.
        """
        query = (
            db.query(ActualProgressLedger, Activity, ExecutionEvent)
            .join(Activity, ActualProgressLedger.activity_id == Activity.id)
            .join(ExecutionEvent, ActualProgressLedger.execution_event_id == ExecutionEvent.id)
            .filter(
                ActualProgressLedger.project_id == project_id,
                ActualProgressLedger.installed_quantity.isnot(None),
                ActualProgressLedger.installed_quantity > 0,
            )
        )

        if activity_code:
            query = query.filter(Activity.activity_code.ilike(f"%{activity_code.strip()}%"))
        if discipline:
            query = query.filter(
                or_(
                    ExecutionEvent.discipline.ilike(f"%{discipline.strip()}%"),
                    Activity.discipline.ilike(f"%{discipline.strip()}%"),
                )
            )
        if contractor:
            query = query.filter(
                or_(
                    ExecutionEvent.contractor.ilike(f"%{contractor.strip()}%"),
                    Activity.contractor_name.ilike(f"%{contractor.strip()}%"),
                )
            )
        if unit:
            query = query.filter(ActualProgressLedger.unit_of_measure.ilike(unit.strip()))
        if from_date:
            query = query.filter(ActualProgressLedger.reporting_date >= from_date)
        if to_date:
            query = query.filter(ActualProgressLedger.reporting_date <= to_date)

        records = query.all()
        if not records:
            return []

        # Group records by (discipline, contractor, activity_code, unit)
        grouped: Dict[Tuple[Optional[str], Optional[str], Optional[str], str], List[Any]] = {}

        for ledger, act, ev in records:
            rec_unit = (ledger.unit_of_measure or act.quantity_unit or "unit").strip()
            rec_disc = (ev.discipline or act.discipline or "General").strip()
            rec_contr = (ev.contractor or act.contractor_name)
            if rec_contr:
                rec_contr = rec_contr.strip()
            rec_code = act.activity_code.strip() if activity_code else None

            # If user queried a specific activity_code, preserve code in key; otherwise group by discipline & unit
            key = (rec_disc, rec_contr if contractor else None, rec_code, rec_unit)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append((ledger, act, ev))

        metrics: List[ProductivityMetricDTO] = []
        for (grp_disc, grp_contr, grp_code, grp_unit), rows in grouped.items():
            total_qty = sum(r[0].installed_quantity for r in rows if r[0].installed_quantity is not None)
            # Distinct reporting days (date part)
            distinct_days = len(
                set(
                    r[0].reporting_date.strftime("%Y-%m-%d")
                    for r in rows
                    if r[0].reporting_date
                )
            )
            reporting_days = max(1, distinct_days)
            rate = round(total_qty / reporting_days, 2)

            evidence_refs: List[EvidenceReferenceDTO] = []
            for r_ledger, r_act, r_ev in rows:
                evidence_refs.append(
                    EvidenceReferenceDTO(
                        execution_event_id=r_ev.id,
                        ledger_id=r_ledger.id,
                        activity_code=r_act.activity_code,
                        activity_name=r_act.name,
                        reporting_date=r_ledger.reporting_date.strftime("%Y-%m-%d")
                        if r_ledger.reporting_date
                        else "",
                        quantity=r_ledger.installed_quantity,
                        unit=r_ledger.unit_of_measure or r_act.quantity_unit,
                        source_type=r_ev.source_type,
                        source_document_name=r_ev.source_document_name,
                        verbatim_excerpt=r_ev.verbatim_excerpt,
                        confidence=r_ev.extraction_confidence,
                    )
                )

            metrics.append(
                ProductivityMetricDTO(
                    discipline=grp_disc,
                    contractor=grp_contr,
                    activity_code=grp_code,
                    unit=f"{grp_unit}/reporting-day",
                    total_quantity=round(total_qty, 2),
                    reporting_days=reporting_days,
                    rate=rate,
                    sample_count=len(rows),
                    formula="Total installed quantity ÷ Distinct reporting days",
                    evidence=evidence_refs,
                )
            )

        return metrics

    @classmethod
    def calculate_durations(
        cls,
        db: Session,
        project_id: str,
        discipline: Optional[str] = None,
        activity_code: Optional[str] = None,
    ) -> DurationSummaryDTO:
        """
        Calculates planned vs actual duration metrics for completed activities.
        Excludes incomplete activities from completed metrics.
        Guards against division-by-zero.
        """
        query = db.query(Activity).filter(
            Activity.project_id == project_id,
            Activity.status == "COMPLETED",
            Activity.actual_start.isnot(None),
            Activity.actual_finish.isnot(None),
        )

        if activity_code:
            query = query.filter(Activity.activity_code.ilike(f"%{activity_code.strip()}%"))
        if discipline:
            query = query.filter(Activity.discipline.ilike(f"%{discipline.strip()}%"))

        activities = query.all()
        if not activities:
            return DurationSummaryDTO(
                activities_completed=0,
                average_planned_duration=0.0,
                average_actual_duration=0.0,
                average_variance_days=0.0,
                on_time_count=0,
                delayed_count=0,
                p50_duration=None,
                p80_duration=None,
                items=[],
            )

        items: List[DurationMetricDTO] = []
        actual_durations: List[float] = []
        planned_durations: List[float] = []
        variances: List[float] = []
        on_time_count = 0

        for act in activities:
            # 1. Planned duration
            if act.original_duration is not None and act.original_duration > 0:
                planned_days = float(act.original_duration)
            elif act.planned_start and act.planned_finish:
                planned_days = max(1.0, (act.planned_finish - act.planned_start).total_seconds() / 86400.0)
            else:
                planned_days = 1.0

            # 2. Actual duration (calendar days)
            diff_sec = (act.actual_finish - act.actual_start).total_seconds()
            actual_days = max(1.0, round(diff_sec / 86400.0, 1))

            # 3. Variance
            variance_days = round(actual_days - planned_days, 1)
            # Guard against division by zero
            safe_planned = planned_days if planned_days > 0 else 1.0
            variance_pct = round((variance_days / safe_planned) * 100.0, 1)
            is_on_time = actual_days <= planned_days

            if is_on_time:
                on_time_count += 1

            actual_durations.append(actual_days)
            planned_durations.append(planned_days)
            variances.append(variance_days)

            items.append(
                DurationMetricDTO(
                    activity_id=act.id,
                    activity_code=act.activity_code,
                    activity_name=act.name,
                    discipline=act.discipline,
                    contractor=act.contractor_name,
                    planned_duration_days=round(planned_days, 1),
                    actual_duration_days=actual_days,
                    variance_days=variance_days,
                    variance_percent=variance_pct,
                    is_on_time=is_on_time,
                    actual_start=act.actual_start.strftime("%Y-%m-%d"),
                    actual_finish=act.actual_finish.strftime("%Y-%m-%d"),
                )
            )

        count = len(items)
        avg_planned = round(sum(planned_durations) / count, 1) if count > 0 else 0.0
        avg_actual = round(sum(actual_durations) / count, 1) if count > 0 else 0.0
        avg_variance = round(sum(variances) / count, 1) if count > 0 else 0.0

        p50 = None
        p80 = None
        if count >= MIN_PERCENTILE_SAMPLE_SIZE:
            sorted_actuals = sorted(actual_durations)
            # P50 (median)
            mid = count // 2
            if count % 2 == 0:
                p50 = round((sorted_actuals[mid - 1] + sorted_actuals[mid]) / 2.0, 1)
            else:
                p50 = round(sorted_actuals[mid], 1)
            # P80
            idx_80 = int(math.ceil(0.8 * count)) - 1
            p80 = round(sorted_actuals[min(max(0, idx_80), count - 1)], 1)

        return DurationSummaryDTO(
            activities_completed=count,
            average_planned_duration=avg_planned,
            average_actual_duration=avg_actual,
            average_variance_days=avg_variance,
            on_time_count=on_time_count,
            delayed_count=count - on_time_count,
            p50_duration=p50,
            p80_duration=p80,
            items=items,
        )

    @classmethod
    def get_project_summary(
        cls,
        db: Session,
        project_id: str,
    ) -> HistoricalSummaryDTO:
        """
        Aggregates high-level execution statistics and data quality metrics for the dashboard.
        """
        # 1. Counts
        verified_event_count = (
            db.query(func.count(ExecutionEvent.id))
            .filter(
                ExecutionEvent.project_id == project_id,
                ExecutionEvent.status.in_(["APPROVED", "APPLIED"]),
            )
            .scalar()
            or 0
        )

        ledger_entry_count = (
            db.query(func.count(ActualProgressLedger.id))
            .filter(ActualProgressLedger.project_id == project_id)
            .scalar()
            or 0
        )

        completed_activity_count = (
            db.query(func.count(Activity.id))
            .filter(
                Activity.project_id == project_id,
                Activity.status == "COMPLETED",
            )
            .scalar()
            or 0
        )

        # 2. Total installed quantity by unit
        qty_rows = (
            db.query(
                ActualProgressLedger.unit_of_measure,
                func.sum(ActualProgressLedger.installed_quantity),
            )
            .filter(
                ActualProgressLedger.project_id == project_id,
                ActualProgressLedger.installed_quantity.isnot(None),
            )
            .group_by(ActualProgressLedger.unit_of_measure)
            .all()
        )
        total_by_unit = {
            unit or "unit": round(float(total), 2)
            for unit, total in qty_rows
            if total is not None
        }

        # 3. Durations
        durations = cls.calculate_durations(db, project_id)

        # 4. Top productivities
        top_prods = cls.calculate_productivity(db, project_id)

        # 5. Latest reporting date
        latest_dt = (
            db.query(func.max(ActualProgressLedger.reporting_date))
            .filter(ActualProgressLedger.project_id == project_id)
            .scalar()
        )
        latest_str = latest_dt.strftime("%Y-%m-%d") if latest_dt else None

        # 6. Data quality audit
        records_with_qty = (
            db.query(func.count(ActualProgressLedger.id))
            .filter(
                ActualProgressLedger.project_id == project_id,
                ActualProgressLedger.installed_quantity.isnot(None),
            )
            .scalar()
            or 0
        )
        records_with_units = (
            db.query(func.count(ActualProgressLedger.id))
            .filter(
                ActualProgressLedger.project_id == project_id,
                ActualProgressLedger.unit_of_measure.isnot(None),
                ActualProgressLedger.unit_of_measure != "",
            )
            .scalar()
            or 0
        )
        completed_with_dates = (
            db.query(func.count(Activity.id))
            .filter(
                Activity.project_id == project_id,
                Activity.status == "COMPLETED",
                Activity.actual_start.isnot(None),
                Activity.actual_finish.isnot(None),
            )
            .scalar()
            or 0
        )

        data_quality = {
            "verified_events": verified_event_count,
            "usable_ledger_entries": ledger_entry_count,
            "records_with_quantity": records_with_qty,
            "records_with_valid_units": records_with_units,
            "completed_activities_with_dates": completed_with_dates,
        }

        return HistoricalSummaryDTO(
            verified_event_count=verified_event_count,
            ledger_entry_count=ledger_entry_count,
            completed_activity_count=completed_activity_count,
            total_quantity_by_unit=total_by_unit,
            average_actual_duration=durations.average_actual_duration if durations.activities_completed > 0 else None,
            average_duration_variance=durations.average_variance_days if durations.activities_completed > 0 else None,
            top_productivities=top_prods[:5],
            latest_reporting_date=latest_str,
            data_quality=data_quality,
        )

    @classmethod
    def get_planning_benchmark(
        cls,
        db: Session,
        project_id: str,
        activity_code: Optional[str] = None,
        discipline: Optional[str] = None,
        unit: Optional[str] = None,
    ) -> PlanningBenchmarkDTO:
        """
        Deterministic planning benchmark retrieval.
        Hierarchy:
        1. Exact activity_code match if present
        2. Discipline match
        Enforces MIN_BENCHMARK_SAMPLE_SIZE = 3.
        Never manufactures statistics on sparse data.
        """
        dur_summary = cls.calculate_durations(
            db=db,
            project_id=project_id,
            discipline=discipline,
            activity_code=activity_code,
        )

        prods = cls.calculate_productivity(
            db=db,
            project_id=project_id,
            discipline=discipline,
            activity_code=activity_code,
            unit=unit,
        )

        sample_size = dur_summary.activities_completed
        obs_rate = prods[0].rate if prods else None
        rate_unit = prods[0].unit if prods else None
        evidence_list: List[EvidenceReferenceDTO] = []
        if prods:
            evidence_list.extend(prods[0].evidence[:10])

        if sample_size == 0 and not prods:
            return PlanningBenchmarkDTO(
                activity_code=activity_code,
                discipline=discipline,
                sample_size=0,
                median_actual_duration=None,
                average_actual_duration=None,
                p50_duration=None,
                p80_duration=None,
                observed_rate=None,
                rate_unit=None,
                status="NO_HISTORICAL_BENCHMARK",
                advisory_message="No verified historical execution records found matching the requested criteria.",
                evidence=[],
            )

        if sample_size < MIN_BENCHMARK_SAMPLE_SIZE:
            msg = (
                f"Insufficient historical sample (found {sample_size} completed activity record(s), "
                f"minimum {MIN_BENCHMARK_SAMPLE_SIZE} required for duration benchmark). "
            )
            if obs_rate:
                msg += f"Observed production rate of {obs_rate} {rate_unit} is available across {prods[0].reporting_days} reporting day(s)."
            else:
                msg += "More execution records are required before establishing an authoritative historical benchmark."

            return PlanningBenchmarkDTO(
                activity_code=activity_code,
                discipline=discipline,
                sample_size=sample_size,
                median_actual_duration=dur_summary.p50_duration,
                average_actual_duration=dur_summary.average_actual_duration if sample_size > 0 else None,
                p50_duration=dur_summary.p50_duration,
                p80_duration=dur_summary.p80_duration,
                observed_rate=obs_rate,
                rate_unit=rate_unit,
                status="INSUFFICIENT_SAMPLE",
                advisory_message=msg,
                evidence=evidence_list,
            )

        # Sufficient sample
        median_val = dur_summary.p50_duration or dur_summary.average_actual_duration
        advisory = (
            f"Historical completed activities matching criteria had an average actual duration of "
            f"{dur_summary.average_actual_duration} days (median {median_val} days) "
            f"based on {sample_size} verified completed activities."
        )
        if obs_rate:
            advisory += f" Observed production rate: {obs_rate} {rate_unit}."
        advisory += " Review planned durations against current project conditions."

        return PlanningBenchmarkDTO(
            activity_code=activity_code,
            discipline=discipline,
            sample_size=sample_size,
            median_actual_duration=median_val,
            average_actual_duration=dur_summary.average_actual_duration,
            p50_duration=dur_summary.p50_duration,
            p80_duration=dur_summary.p80_duration,
            observed_rate=obs_rate,
            rate_unit=rate_unit,
            status="SUFFICIENT_SAMPLE",
            advisory_message=advisory,
            evidence=evidence_list,
        )
