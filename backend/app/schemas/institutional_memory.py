from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class EvidenceReferenceDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    execution_event_id: str
    ledger_id: Optional[str] = None
    activity_code: str
    activity_name: Optional[str] = None
    reporting_date: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    source_type: Optional[str] = None
    source_document_name: Optional[str] = None
    verbatim_excerpt: Optional[str] = None
    confidence: Optional[float] = None


class HistoricalLedgerEntryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ledger_id: str
    execution_event_id: str
    project_id: str
    project_code: Optional[str] = None
    activity_id: str
    activity_code: str
    activity_name: str
    reporting_date: str
    installed_quantity: Optional[float] = None
    unit_of_measure: Optional[str] = None
    incremental_percent: Optional[float] = None
    cumulative_percent: float
    status_reported: Optional[str] = None
    source_type: Optional[str] = None
    discipline: Optional[str] = None
    contractor: Optional[str] = None
    location: Optional[str] = None
    source_document_name: Optional[str] = None
    artifact_id: Optional[str] = None
    created_at: str


class HistoricalLedgerPageDTO(BaseModel):
    items: List[HistoricalLedgerEntryDTO]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProductivityMetricDTO(BaseModel):
    discipline: Optional[str] = None
    contractor: Optional[str] = None
    activity_code: Optional[str] = None
    unit: str
    total_quantity: float
    reporting_days: int
    rate: float
    sample_count: int
    formula: str = "Total installed quantity ÷ Distinct reporting days"
    evidence: List[EvidenceReferenceDTO] = []


class DurationMetricDTO(BaseModel):
    activity_id: str
    activity_code: str
    activity_name: str
    discipline: Optional[str] = None
    contractor: Optional[str] = None
    planned_duration_days: float
    actual_duration_days: float
    variance_days: float
    variance_percent: float
    is_on_time: bool
    actual_start: str
    actual_finish: str


class DurationSummaryDTO(BaseModel):
    activities_completed: int
    average_planned_duration: float
    average_actual_duration: float
    average_variance_days: float
    on_time_count: int
    delayed_count: int
    p50_duration: Optional[float] = None
    p80_duration: Optional[float] = None
    items: List[DurationMetricDTO] = []


class HistoricalInsightDTO(BaseModel):
    insight_type: str  # "PRODUCTIVITY" | "DURATION_VARIANCE" | "EXECUTION_PATTERN"
    title: str
    summary: str
    metric_value: Optional[float] = None
    unit: Optional[str] = None
    sample_size: int
    reporting_days: Optional[int] = None
    evidence: List[EvidenceReferenceDTO] = []
    limitations: List[str] = []


class PlanningBenchmarkDTO(BaseModel):
    activity_code: Optional[str] = None
    discipline: Optional[str] = None
    sample_size: int
    median_actual_duration: Optional[float] = None
    average_actual_duration: Optional[float] = None
    p50_duration: Optional[float] = None
    p80_duration: Optional[float] = None
    observed_rate: Optional[float] = None
    rate_unit: Optional[str] = None
    status: str  # "SUFFICIENT_SAMPLE" | "INSUFFICIENT_SAMPLE" | "NO_HISTORICAL_BENCHMARK"
    advisory_message: str
    evidence: List[EvidenceReferenceDTO] = []


class HistoricalSummaryDTO(BaseModel):
    verified_event_count: int
    ledger_entry_count: int
    completed_activity_count: int
    total_quantity_by_unit: Dict[str, float]
    average_actual_duration: Optional[float] = None
    average_duration_variance: Optional[float] = None
    top_productivities: List[ProductivityMetricDTO] = []
    latest_reporting_date: Optional[str] = None
    data_quality: Dict[str, Any] = {}


class HistoricalQueryRequest(BaseModel):
    query_type: str = "PRODUCTIVITY"  # "PRODUCTIVITY" | "DURATION" | "VARIANCE" | "EXECUTION_HISTORY" | "SUMMARY"
    activity_code: Optional[str] = None
    discipline: Optional[str] = None
    contractor: Optional[str] = None
    location: Optional[str] = None
    unit: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    natural_query: Optional[str] = None


class HistoricalQueryResponse(BaseModel):
    query_type: str
    summary: str
    metrics: List[Dict[str, Any]] = []
    insights: List[HistoricalInsightDTO] = []
    evidence: List[EvidenceReferenceDTO] = []
    data_status: str = "CONFIRMED"  # "CONFIRMED" | "INSUFFICIENT_DATA" | "NO_RECORDS"
