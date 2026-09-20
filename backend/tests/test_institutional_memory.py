from datetime import datetime, timedelta
import pytest
from app.domain.models import (
    Activity,
    ActualProgressLedger,
    Artifact,
    Conversation,
    ExecutionEvent,
    Project,
    ScheduleAuditLog,
    WBSNode,
)
from app.schemas.institutional_memory import (
    HistoricalQueryRequest,
    HistoricalQueryResponse,
)
from app.services.agent_service import TimeAgentService
from app.services.historical_analytics_service import HistoricalAnalyticsService
from app.services.institutional_memory_service import InstitutionalMemoryService


def seed_memory_data(db_session):
    """
    Seeds a project with verified execution events, progress ledger rows, and completed activities.
    """
    proj = Project(
        id="proj-mem-1",
        project_code="BOROUGE4_TEST",
        name="Borouge 4 Test Project",
        data_date=datetime(2026, 9, 20),
    )
    wbs = WBSNode(
        id="wbs-mem-1",
        project_id="proj-mem-1",
        code="WBS-01",
        name="Site Works",
    )

    # Completed activities
    act1 = Activity(
        id="act-civ-1",
        project_id="proj-mem-1",
        wbs_id="wbs-mem-1",
        activity_code="CIV-1001",
        name="Foundation Pouring",
        discipline="Civil",
        contractor_name="Al-Futtaim",
        status="COMPLETED",
        percent_complete=100.0,
        planned_start=datetime(2026, 9, 1),
        planned_finish=datetime(2026, 9, 6),
        original_duration=5.0,
        actual_start=datetime(2026, 9, 1),
        actual_finish=datetime(2026, 9, 7),  # 6 days actual (+1 day variance)
    )

    act2 = Activity(
        id="act-pip-1",
        project_id="proj-mem-1",
        wbs_id="wbs-mem-1",
        activity_code="PIP-2001",
        name="Spool Erection",
        discipline="Piping",
        contractor_name="Dodsal",
        status="COMPLETED",
        percent_complete=100.0,
        planned_start=datetime(2026, 9, 5),
        planned_finish=datetime(2026, 9, 15),
        original_duration=10.0,
        actual_start=datetime(2026, 9, 5),
        actual_finish=datetime(2026, 9, 14),  # 9 days actual (-1 day on time)
    )

    # In-progress activity (should be excluded from completed duration metrics)
    act3 = Activity(
        id="act-ele-1",
        project_id="proj-mem-1",
        wbs_id="wbs-mem-1",
        activity_code="ELE-3001",
        name="Cable Pulling",
        discipline="Electrical",
        contractor_name="Siemens",
        status="IN_PROGRESS",
        percent_complete=45.0,
        planned_start=datetime(2026, 9, 10),
        planned_finish=datetime(2026, 9, 20),
        original_duration=10.0,
        actual_start=datetime(2026, 9, 10),
        actual_finish=None,
    )

    # Execution Events
    ev1 = ExecutionEvent(
        id="ev-mem-1",
        project_id="proj-mem-1",
        source_type="CONVERSATION",
        verbatim_excerpt="Poured 35 m3 concrete for CIV-1001",
        description="Concrete pour",
        execution_date=datetime(2026, 9, 2),
        status_reported="IN_PROGRESS",
        quantity=35.0,
        unit="m3",
        discipline="Civil",
        contractor="Al-Futtaim",
        extraction_confidence=0.95,
        status="APPLIED",
        matched_activity_id="act-civ-1",
    )

    ev2 = ExecutionEvent(
        id="ev-mem-2",
        project_id="proj-mem-1",
        source_type="ARTIFACT",
        source_document_name="Daily_Piping_Report.pdf",
        verbatim_excerpt="Installed 10 m pipe on Day 1",
        description="Piping installation",
        execution_date=datetime(2026, 9, 6),
        status_reported="IN_PROGRESS",
        quantity=10.0,
        unit="m",
        discipline="Piping",
        contractor="Dodsal",
        extraction_confidence=0.9,
        status="APPLIED",
        matched_activity_id="act-pip-1",
    )

    ev3 = ExecutionEvent(
        id="ev-mem-3",
        project_id="proj-mem-1",
        source_type="ARTIFACT",
        source_document_name="Daily_Piping_Report.pdf",
        verbatim_excerpt="Installed 15 m pipe on Day 2",
        description="Piping installation",
        execution_date=datetime(2026, 9, 7),
        status_reported="IN_PROGRESS",
        quantity=15.0,
        unit="m",
        discipline="Piping",
        contractor="Dodsal",
        extraction_confidence=0.9,
        status="APPLIED",
        matched_activity_id="act-pip-1",
    )

    ev4 = ExecutionEvent(
        id="ev-mem-4",
        project_id="proj-mem-1",
        source_type="ARTIFACT",
        source_document_name="Daily_Piping_Report.pdf",
        verbatim_excerpt="Installed 12 m pipe on Day 3",
        description="Piping installation",
        execution_date=datetime(2026, 9, 8),
        status_reported="IN_PROGRESS",
        quantity=12.0,
        unit="m",
        discipline="Piping",
        contractor="Dodsal",
        extraction_confidence=0.9,
        status="APPLIED",
        matched_activity_id="act-pip-1",
    )

    # Actual Progress Ledger Rows
    led1 = ActualProgressLedger(
        id="led-1",
        project_id="proj-mem-1",
        activity_id="act-civ-1",
        execution_event_id="ev-mem-1",
        reporting_date=datetime(2026, 9, 2),
        installed_quantity=35.0,
        unit_of_measure="m3",
        incremental_percent=50.0,
        cumulative_percent=50.0,
    )

    led2 = ActualProgressLedger(
        id="led-2",
        project_id="proj-mem-1",
        activity_id="act-pip-1",
        execution_event_id="ev-mem-2",
        reporting_date=datetime(2026, 9, 6),
        installed_quantity=10.0,
        unit_of_measure="m",
        incremental_percent=25.0,
        cumulative_percent=25.0,
    )

    led3 = ActualProgressLedger(
        id="led-3",
        project_id="proj-mem-1",
        activity_id="act-pip-1",
        execution_event_id="ev-mem-3",
        reporting_date=datetime(2026, 9, 7),
        installed_quantity=15.0,
        unit_of_measure="m",
        incremental_percent=35.0,
        cumulative_percent=60.0,
    )

    led4 = ActualProgressLedger(
        id="led-4",
        project_id="proj-mem-1",
        activity_id="act-pip-1",
        execution_event_id="ev-mem-4",
        reporting_date=datetime(2026, 9, 8),
        installed_quantity=12.0,
        unit_of_measure="m",
        incremental_percent=40.0,
        cumulative_percent=100.0,
    )

    db_session.add_all([proj, wbs, act1, act2, act3, ev1, ev2, ev3, ev4, led1, led2, led3, led4])
    db_session.commit()
    return proj


def test_ledger_returns_verified_records_and_pagination(db_session):
    seed_memory_data(db_session)
    res = HistoricalAnalyticsService.get_ledger_entries(
        db=db_session,
        project_id="proj-mem-1",
        page=1,
        page_size=2,
    )
    assert res.total == 4
    assert len(res.items) == 2
    assert res.total_pages == 2
    assert res.items[0].activity_code in ["PIP-2001", "CIV-1001"]
    assert res.items[0].cumulative_percent > 0


def test_ledger_project_isolation(db_session):
    seed_memory_data(db_session)
    res = HistoricalAnalyticsService.get_ledger_entries(
        db=db_session,
        project_id="other-non-existent-proj",
        page=1,
        page_size=10,
    )
    assert res.total == 0
    assert len(res.items) == 0


def test_ledger_filtering_by_discipline_and_unit(db_session):
    seed_memory_data(db_session)
    res_civ = HistoricalAnalyticsService.get_ledger_entries(
        db=db_session,
        project_id="proj-mem-1",
        discipline="Civil",
    )
    assert res_civ.total == 1
    assert res_civ.items[0].activity_code == "CIV-1001"
    assert res_civ.items[0].unit_of_measure == "m3"

    res_pip = HistoricalAnalyticsService.get_ledger_entries(
        db=db_session,
        project_id="proj-mem-1",
        unit="m",
    )
    assert res_pip.total == 3
    for it in res_pip.items:
        assert it.unit_of_measure == "m"


def test_productivity_single_event_rate(db_session):
    seed_memory_data(db_session)
    prods = HistoricalAnalyticsService.calculate_productivity(
        db=db_session,
        project_id="proj-mem-1",
        discipline="Civil",
    )
    assert len(prods) == 1
    civ = prods[0]
    assert civ.discipline == "Civil"
    assert civ.total_quantity == 35.0
    assert civ.reporting_days == 1
    assert civ.rate == 35.0
    assert civ.unit == "m3/reporting-day"
    assert len(civ.evidence) == 1
    assert civ.evidence[0].execution_event_id == "ev-mem-1"


def test_productivity_multiple_reporting_days_and_distinct_days(db_session):
    """
    Prompt requirement:
    10 m on Day 1, 15 m on Day 2, 12 m on Day 3
    -> 37 m total / 3 reporting days = 12.33 m/reporting-day
    """
    seed_memory_data(db_session)
    prods = HistoricalAnalyticsService.calculate_productivity(
        db=db_session,
        project_id="proj-mem-1",
        discipline="Piping",
    )
    assert len(prods) == 1
    pip = prods[0]
    assert pip.discipline == "Piping"
    assert pip.total_quantity == 37.0
    assert pip.reporting_days == 3
    assert pip.rate == 12.33
    assert pip.unit == "m/reporting-day"
    assert pip.sample_count == 3
    assert len(pip.evidence) == 3


def test_productivity_segregates_incompatible_units(db_session):
    """
    Prompt requirement: Incompatible units like m and m3 must never be combined into one rate.
    """
    seed_memory_data(db_session)
    all_prods = HistoricalAnalyticsService.calculate_productivity(
        db=db_session,
        project_id="proj-mem-1",
    )
    assert len(all_prods) == 2
    units = [p.unit for p in all_prods]
    assert "m/reporting-day" in units
    assert "m3/reporting-day" in units


def test_duration_planned_vs_actual_and_variance(db_session):
    seed_memory_data(db_session)
    durs = HistoricalAnalyticsService.calculate_durations(
        db=db_session,
        project_id="proj-mem-1",
    )
    # Only completed activities with actual_start and actual_finish: CIV-1001 and PIP-2001
    assert durs.activities_completed == 2
    items_by_code = {item.activity_code: item for item in durs.items}

    # CIV-1001: 5d planned, 6d actual -> +1.0d variance (late)
    civ = items_by_code["CIV-1001"]
    assert civ.planned_duration_days == 5.0
    assert civ.actual_duration_days == 6.0
    assert civ.variance_days == 1.0
    assert civ.variance_percent == 20.0
    assert civ.is_on_time is False

    # PIP-2001: 10d planned, 9d actual -> -1.0d variance (on time)
    pip = items_by_code["PIP-2001"]
    assert pip.planned_duration_days == 10.0
    assert pip.actual_duration_days == 9.0
    assert pip.variance_days == -1.0
    assert pip.variance_percent == -10.0
    assert pip.is_on_time is True

    assert durs.on_time_count == 1
    assert durs.delayed_count == 1
    # Sample < 5 so percentiles should be None
    assert durs.p50_duration is None
    assert durs.p80_duration is None


def test_duration_incomplete_activity_excluded(db_session):
    seed_memory_data(db_session)
    durs = HistoricalAnalyticsService.calculate_durations(
        db=db_session,
        project_id="proj-mem-1",
    )
    # ELE-3001 is IN_PROGRESS so it must NOT be included in completed metrics
    codes = [item.activity_code for item in durs.items]
    assert "ELE-3001" not in codes


def test_institutional_memory_service_query_productivity(db_session):
    seed_memory_data(db_session)
    req = HistoricalQueryRequest(
        query_type="PRODUCTIVITY",
        discipline="Piping",
    )
    res = InstitutionalMemoryService.execute_query(
        db=db_session,
        project_id="proj-mem-1",
        request=req,
    )
    assert res.query_type == "PRODUCTIVITY"
    assert res.data_status == "CONFIRMED"
    assert "12.33 m/reporting-day" in res.summary
    assert len(res.evidence) == 3
    assert len(res.insights) == 1
    assert res.insights[0].metric_value == 12.33


def test_institutional_memory_service_query_insufficient_data(db_session):
    seed_memory_data(db_session)
    req = HistoricalQueryRequest(
        query_type="PRODUCTIVITY",
        discipline="Civil",
    )
    res = InstitutionalMemoryService.execute_query(
        db=db_session,
        project_id="proj-mem-1",
        request=req,
    )
    # Civil only has 1 reporting day in seed data
    assert res.data_status == "INSUFFICIENT_DATA"
    assert "More execution records are needed" in res.summary


def test_planning_benchmark_advisory_without_mutation(db_session):
    seed_memory_data(db_session)
    bm = HistoricalAnalyticsService.get_planning_benchmark(
        db=db_session,
        project_id="proj-mem-1",
        discipline="Civil",
    )
    assert bm.discipline == "Civil"
    assert bm.status in ["INSUFFICIENT_SAMPLE", "SUFFICIENT_SAMPLE"]
    assert "advisory" in bm.advisory_message.lower() or "benchmark" in bm.advisory_message.lower()


def test_csv_export_format_and_headers(db_session):
    seed_memory_data(db_session)
    csv_str = InstitutionalMemoryService.export_ledger_csv(
        db=db_session,
        project_id="proj-mem-1",
    )
    lines = csv_str.strip().split("\r\n")
    if len(lines) == 1:
        lines = csv_str.strip().split("\n")
    header = lines[0]
    assert "Project Code" in header
    assert "Activity Code" in header
    assert "Installed Quantity" in header
    assert "Unit" in header
    assert "Ledger ID" in header
    assert len(lines) == 5  # header + 4 rows


def test_time_agent_historical_tool_returns_grounded_data(db_session):
    seed_memory_data(db_session)
    tool_res = TimeAgentService.query_historical_performance(
        db=db_session,
        project_id="proj-mem-1",
        query_type="PRODUCTIVITY",
        discipline="Piping",
    )
    assert tool_res["query_type"] == "PRODUCTIVITY"
    assert "12.33" in tool_res["summary"]
    assert len(tool_res["evidence"]) == 3


def test_api_endpoints_via_client(client, db_session):
    seed_memory_data(db_session)

    # 1. Summary
    res = client.get("/api/v1/projects/proj-mem-1/institutional-memory/summary")
    assert res.status_code == 200
    s_data = res.json()
    assert s_data["verified_event_count"] == 4
    assert s_data["ledger_entry_count"] == 4
    assert s_data["completed_activity_count"] == 2

    # 2. Ledger
    res = client.get("/api/v1/projects/proj-mem-1/institutional-memory/ledger")
    assert res.status_code == 200
    l_data = res.json()
    assert l_data["total"] == 4

    # 3. Productivity
    res = client.get("/api/v1/projects/proj-mem-1/institutional-memory/productivity?discipline=Piping")
    assert res.status_code == 200
    p_data = res.json()
    assert len(p_data) == 1
    assert p_data[0]["rate"] == 12.33

    # 4. Durations
    res = client.get("/api/v1/projects/proj-mem-1/institutional-memory/durations")
    assert res.status_code == 200
    d_data = res.json()
    assert d_data["activities_completed"] == 2

    # 5. Benchmarks
    res = client.get("/api/v1/projects/proj-mem-1/institutional-memory/benchmarks?discipline=Civil")
    assert res.status_code == 200

    # 6. Query POST
    res = client.post(
        "/api/v1/projects/proj-mem-1/institutional-memory/query",
        json={"query_type": "PRODUCTIVITY", "discipline": "Piping"},
    )
    assert res.status_code == 200
    q_data = res.json()
    assert "12.33" in q_data["summary"]

    # 7. CSV Export
    res = client.get("/api/v1/projects/proj-mem-1/institutional-memory/ledger/export")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "Project Code" in res.text
