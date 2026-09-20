from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.domain.models import Project
from app.schemas.institutional_memory import (
    EvidenceReferenceDTO,
    HistoricalInsightDTO,
    HistoricalQueryRequest,
    HistoricalQueryResponse,
)
from app.services.historical_analytics_service import HistoricalAnalyticsService

logger = logging.getLogger("institutional_memory_service")


class InstitutionalMemoryService:
    @classmethod
    def execute_query(
        cls,
        db: Session,
        project_id: str,
        request: HistoricalQueryRequest,
    ) -> HistoricalQueryResponse:
        """
        Executes a structured historical knowledge query.
        Guarantees that all metrics originate deterministically from PostgreSQL.
        The LLM never computes or discovers authoritative numbers.
        """
        qtype = (request.query_type or "PRODUCTIVITY").strip().upper()

        # Handle natural language pre-parsing if natural_query is supplied without structured filters
        if request.natural_query and not (request.discipline or request.activity_code or request.contractor):
            cls._extract_query_filters_from_text(request)

        if qtype == "PRODUCTIVITY":
            prods = HistoricalAnalyticsService.calculate_productivity(
                db=db,
                project_id=project_id,
                discipline=request.discipline,
                contractor=request.contractor,
                activity_code=request.activity_code,
                unit=request.unit,
                from_date=request.from_date,
                to_date=request.to_date,
            )
            if not prods:
                return HistoricalQueryResponse(
                    query_type=qtype,
                    summary="No verified progress records with quantity measurements found for the specified criteria.",
                    metrics=[],
                    insights=[],
                    evidence=[],
                    data_status="NO_RECORDS",
                )

            top = prods[0]
            if top.reporting_days < 2 and top.sample_count < 3:
                status = "INSUFFICIENT_DATA"
                summary = (
                    f"Found {top.sample_count} verified progress record(s) across only {top.reporting_days} reporting day "
                    f"for {top.discipline or 'work'}. Current recorded quantity is {top.total_quantity} {top.unit.replace('/reporting-day', '')}, "
                    f"yielding an observed rate of {top.rate} {top.unit}. More execution records are needed for a dependable historical baseline."
                )
            else:
                status = "CONFIRMED"
                disc_label = f"{top.discipline} " if top.discipline else ""
                contr_label = f"by {top.contractor} " if top.contractor else ""
                summary = (
                    f"Based on {top.sample_count} verified progress records across {top.reporting_days} distinct reporting days, "
                    f"the observed {disc_label}production rate {contr_label}was approximately {top.rate} {top.unit}."
                )

            insight = HistoricalInsightDTO(
                insight_type="PRODUCTIVITY",
                title=f"Observed {top.discipline or 'Work'} Production Rate",
                summary=summary,
                metric_value=top.rate,
                unit=top.unit,
                sample_size=top.sample_count,
                reporting_days=top.reporting_days,
                evidence=top.evidence,
                limitations=["Observed rate based on recorded reporting days.", top.formula],
            )

            metrics_list = [p.model_dump() for p in prods]
            all_evidence: List[EvidenceReferenceDTO] = []
            for p in prods:
                all_evidence.extend(p.evidence)

            return HistoricalQueryResponse(
                query_type=qtype,
                summary=summary,
                metrics=metrics_list,
                insights=[insight],
                evidence=all_evidence[:25],
                data_status=status,
            )

        elif qtype in ["DURATION", "VARIANCE"]:
            dur_summary = HistoricalAnalyticsService.calculate_durations(
                db=db,
                project_id=project_id,
                discipline=request.discipline,
                activity_code=request.activity_code,
            )

            if dur_summary.activities_completed == 0:
                return HistoricalQueryResponse(
                    query_type=qtype,
                    summary="No completed activities with verified start and finish dates found for the specified criteria.",
                    metrics=[],
                    insights=[],
                    evidence=[],
                    data_status="NO_RECORDS",
                )

            avg_act = dur_summary.average_actual_duration
            avg_plan = dur_summary.average_planned_duration
            avg_var = dur_summary.average_variance_days
            count = dur_summary.activities_completed

            status = "CONFIRMED" if count >= 3 else "INSUFFICIENT_DATA"
            var_str = f"+{avg_var}" if avg_var > 0 else f"{avg_var}"
            summary = (
                f"Among {count} completed activities, the average actual duration was {avg_act} calendar days "
                f"versus {avg_plan} planned days (average variance of {var_str} days). "
                f"{dur_summary.on_time_count} activities were completed on time, and {dur_summary.delayed_count} were delayed."
            )

            insight = HistoricalInsightDTO(
                insight_type="DURATION_VARIANCE",
                title="Planned vs Actual Duration Variance",
                summary=summary,
                metric_value=avg_act,
                unit="calendar days",
                sample_size=count,
                reporting_days=None,
                evidence=[],
                limitations=["Only includes fully completed activities with recorded actual start and finish dates."],
            )

            return HistoricalQueryResponse(
                query_type=qtype,
                summary=summary,
                metrics=[dur_summary.model_dump()],
                insights=[insight],
                evidence=[],
                data_status=status,
            )

        elif qtype == "EXECUTION_HISTORY":
            ledger_page = HistoricalAnalyticsService.get_ledger_entries(
                db=db,
                project_id=project_id,
                activity_code=request.activity_code,
                discipline=request.discipline,
                contractor=request.contractor,
                location=request.location,
                unit=request.unit,
                from_date=request.from_date,
                to_date=request.to_date,
                page=1,
                page_size=20,
            )
            summary = f"Found {ledger_page.total} verified execution progress records in the historical ledger."
            evidence = [
                EvidenceReferenceDTO(
                    execution_event_id=item.execution_event_id,
                    ledger_id=item.ledger_id,
                    activity_code=item.activity_code,
                    activity_name=item.activity_name,
                    reporting_date=item.reporting_date,
                    quantity=item.installed_quantity,
                    unit=item.unit_of_measure,
                    source_type=item.source_type,
                    source_document_name=item.source_document_name,
                    verbatim_excerpt=None,
                    confidence=None,
                )
                for item in ledger_page.items
            ]
            return HistoricalQueryResponse(
                query_type=qtype,
                summary=summary,
                metrics=[{"total_records": ledger_page.total}],
                insights=[],
                evidence=evidence,
                data_status="CONFIRMED" if ledger_page.total > 0 else "NO_RECORDS",
            )

        else:  # SUMMARY
            proj_summary = HistoricalAnalyticsService.get_project_summary(db, project_id)
            summary = (
                f"Project history contains {proj_summary.verified_event_count} verified execution events, "
                f"{proj_summary.ledger_entry_count} progress ledger entries, and {proj_summary.completed_activity_count} completed activities."
            )
            return HistoricalQueryResponse(
                query_type="SUMMARY",
                summary=summary,
                metrics=[proj_summary.model_dump()],
                insights=[],
                evidence=[],
                data_status="CONFIRMED" if proj_summary.ledger_entry_count > 0 else "NO_RECORDS",
            )

    @classmethod
    def generate_insights(
        cls,
        db: Session,
        project_id: str,
    ) -> List[HistoricalInsightDTO]:
        """
        Generates grounded, evidence-based institutional insight cards for the dashboard.
        """
        insights: List[HistoricalInsightDTO] = []

        # 1. Productivity insights
        prods = HistoricalAnalyticsService.calculate_productivity(db=db, project_id=project_id)
        for p in prods[:3]:
            disc_label = f"{p.discipline} " if p.discipline else ""
            contr_label = f"({p.contractor}) " if p.contractor else ""
            summary = (
                f"Verified records demonstrate an observed {disc_label}production rate {contr_label}of "
                f"{p.rate} {p.unit} across {p.reporting_days} reporting day(s) ({p.sample_count} progress events)."
            )
            insights.append(
                HistoricalInsightDTO(
                    insight_type="PRODUCTIVITY",
                    title=f"Observed {p.discipline or 'Discipline'} Rate",
                    summary=summary,
                    metric_value=p.rate,
                    unit=p.unit,
                    sample_size=p.sample_count,
                    reporting_days=p.reporting_days,
                    evidence=p.evidence[:10],
                    limitations=["Rate derived strictly from verified applied quantities over distinct reporting dates."],
                )
            )

        # 2. Duration insights
        durs = HistoricalAnalyticsService.calculate_durations(db=db, project_id=project_id)
        if durs.activities_completed > 0:
            var_sign = "+" if durs.average_variance_days > 0 else ""
            d_summary = (
                f"Completed activities averaged {durs.average_actual_duration} days actual duration versus "
                f"{durs.average_planned_duration} days planned (average variance {var_sign}{durs.average_variance_days} days). "
                f"{durs.on_time_count} of {durs.activities_completed} completed on time."
            )
            insights.append(
                HistoricalInsightDTO(
                    insight_type="DURATION_VARIANCE",
                    title="Historical Execution Duration Pacing",
                    summary=d_summary,
                    metric_value=durs.average_actual_duration,
                    unit="days",
                    sample_size=durs.activities_completed,
                    reporting_days=None,
                    evidence=[],
                    limitations=["Includes completed activities with valid actual start and finish dates."],
                )
            )

        return insights

    @classmethod
    def export_ledger_csv(
        cls,
        db: Session,
        project_id: str,
        activity_code: Optional[str] = None,
        discipline: Optional[str] = None,
        contractor: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> str:
        """
        Exports verified execution ledger to RFC 4180 compliant CSV format.
        Never leaks internal credentials.
        """
        ledger_page = HistoricalAnalyticsService.get_ledger_entries(
            db=db,
            project_id=project_id,
            activity_code=activity_code,
            discipline=discipline,
            contractor=contractor,
            from_date=from_date,
            to_date=to_date,
            page=1,
            page_size=10000,
        )

        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # Header row
        writer.writerow(
            [
                "Project Code",
                "Activity Code",
                "Activity Name",
                "Reporting Date",
                "Installed Quantity",
                "Unit",
                "Incremental Percent",
                "Cumulative Percent",
                "Discipline",
                "Contractor",
                "Location",
                "Status Reported",
                "Source Type",
                "Source Document",
                "Execution Event ID",
                "Ledger ID",
                "Created At",
            ]
        )

        for item in ledger_page.items:
            writer.writerow(
                [
                    item.project_code or "",
                    item.activity_code,
                    item.activity_name,
                    item.reporting_date,
                    item.installed_quantity if item.installed_quantity is not None else "",
                    item.unit_of_measure or "",
                    item.incremental_percent if item.incremental_percent is not None else "",
                    item.cumulative_percent,
                    item.discipline or "",
                    item.contractor or "",
                    item.location or "",
                    item.status_reported or "",
                    item.source_type or "",
                    item.source_document_name or "",
                    item.execution_event_id,
                    item.ledger_id,
                    item.created_at,
                ]
            )

        return output.getvalue()

    @classmethod
    def _extract_query_filters_from_text(cls, request: HistoricalQueryRequest) -> None:
        """
        Helper rule-based filter extractor for natural queries.
        """
        txt = (request.natural_query or "").lower()
        if "piping" in txt or "pipe" in txt or "spool" in txt:
            request.discipline = "Piping"
        elif "civil" in txt or "concrete" in txt or "foundation" in txt:
            request.discipline = "Civil"
        elif "electrical" in txt or "cable" in txt or "tray" in txt:
            request.discipline = "Electrical"
        elif "mechanical" in txt or "pump" in txt or "vessel" in txt:
            request.discipline = "Mechanical"

        if "duration" in txt or "long" in txt or "days" in txt or "time" in txt:
            request.query_type = "DURATION"
        elif "variance" in txt or "delay" in txt or "behind" in txt or "late" in txt:
            request.query_type = "VARIANCE"
        elif "rate" in txt or "productivity" in txt or "pour" in txt or "install" in txt:
            request.query_type = "PRODUCTIVITY"
        elif "ledger" in txt or "history" in txt or "records" in txt:
            request.query_type = "EXECUTION_HISTORY"
