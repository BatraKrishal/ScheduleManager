import os
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.models import (
    Activity,
    ActualProgressLedger,
    Conversation,
    ConversationMessage,
    DomainOutbox,
    ExecutionEvent,
    Project,
    ScheduleAuditLog,
    UpdateProposal,
    WBSNode,
)
from app.services.agent_parser import ConversationalParser
from app.services.matching_service import MatchingService
from app.services.schedule_update_service import ScheduleUpdateService
from app.services.agent_service import TimeAgentService
from app.services.validation_service import ValidationException


@pytest.fixture
def agent_test_project(db_session: Session):
    """Creates a sample project with activities for Time Agent testing."""
    proj = Project(
        id="proj-agent-demo",
        project_code="BOROUGE4_DEMO",
        name="Borouge 4 Petrochemical Expansion",
        planned_start=datetime(2024, 1, 1, 8, 0),
        planned_finish=datetime(2025, 12, 31, 17, 0),
        data_date=datetime(2024, 10, 1, 0, 0),
    )
    db_session.add(proj)

    wbs1 = WBSNode(
        id="wbs-agent-1",
        project_id="proj-agent-demo",
        code="WBS-CIV",
        name="Civil Works",
    )
    wbs2 = WBSNode(
        id="wbs-agent-2",
        project_id="proj-agent-demo",
        code="WBS-STR",
        name="Structural Works",
    )
    db_session.add_all([wbs1, wbs2])

    act1 = Activity(
        id="act-civ-1001",
        project_id="proj-agent-demo",
        wbs_id="wbs-agent-1",
        activity_code="CIV-1001",
        name="Foundation Concrete Pour F-204",
        status="NOT_STARTED",
        planned_start=datetime(2024, 8, 1, 8, 0),
        planned_finish=datetime(2024, 9, 30, 17, 0),
        original_duration=60.0,
        percent_complete=0.0,
        planned_quantity=100.0,
        quantity_unit="m3",
    )

    act2 = Activity(
        id="act-civ-1002",
        project_id="proj-agent-demo",
        wbs_id="wbs-agent-1",
        activity_code="CIV-1002",
        name="Foundation Concrete Pour F-205",
        status="NOT_STARTED",
        planned_start=datetime(2024, 8, 1, 8, 0),
        planned_finish=datetime(2024, 9, 30, 17, 0),
        original_duration=60.0,
        percent_complete=0.0,
        planned_quantity=100.0,
        quantity_unit="m3",
    )

    act3 = Activity(
        id="act-str-2001",
        project_id="proj-agent-demo",
        wbs_id="wbs-agent-2",
        activity_code="STR-2001",
        name="Structural Steel Erection Area B",
        status="IN_PROGRESS",
        planned_start=datetime(2024, 9, 1, 8, 0),
        planned_finish=datetime(2024, 11, 30, 17, 0),
        actual_start=datetime(2024, 9, 5, 8, 0),
        original_duration=90.0,
        percent_complete=40.0,
        planned_quantity=200.0,
        quantity_unit="tons",
    )

    db_session.add_all([act1, act2, act3])
    db_session.commit()
    return proj


# =========================================================================
# TEST SUITE A: Conversational Parser & Intent Classification
# =========================================================================

def test_intent_classification_and_offline_fallback():
    parser = ConversationalParser(gemini_api_key=None)
    ref_date = datetime(2024, 10, 1)

    # 1. Information query
    res_info = parser.parse("What is the status of CIV-1001?", reference_date=ref_date)
    assert res_info.intent == "INFORMATION_QUERY"
    assert res_info.reported_activity_code == "CIV-1001"

    # 2. Direct percentage update request
    res_pct = parser.parse("Update CIV-1001 to 80%.", reference_date=ref_date)
    assert res_pct.intent == "PROGRESS_UPDATE_REQUEST"
    assert res_pct.reported_activity_code == "CIV-1001"
    assert res_pct.override_percent == 80.0

    # 3. Progress report
    res_prog = parser.parse("We poured 35 m3 of concrete today for CIV-1001.", reference_date=ref_date)
    assert res_prog.intent == "PROGRESS_REPORT"
    assert res_prog.quantity == 35.0
    assert res_prog.unit == "m3"
    assert res_prog.reported_activity_code == "CIV-1001"
    assert res_prog.execution_date == "today"

    # 4. Clarification answer (activity code in clarification turn)
    res_clar = parser.parse("CIV-1002", reference_date=ref_date, is_clarification_turn=True)
    assert res_clar.intent == "CLARIFICATION_RESPONSE"
    assert res_clar.reported_activity_code == "CIV-1002"


# =========================================================================
# TEST SUITE B: Date Resolution
# =========================================================================

def test_date_resolution():
    ref_date = datetime(2024, 10, 1)  # A Tuesday

    dt_today = ConversationalParser.resolve_date("today", reference_date=ref_date)
    assert dt_today == datetime(2024, 10, 1)

    dt_yesterday = ConversationalParser.resolve_date("yesterday", reference_date=ref_date)
    assert dt_yesterday == datetime(2024, 9, 30)

    dt_explicit = ConversationalParser.resolve_date("2024-09-15", reference_date=ref_date)
    assert dt_explicit == datetime(2024, 9, 15)


# =========================================================================
# TEST SUITE C: Safe Non-Finalizing Evaluation (MatchingService)
# =========================================================================

def test_evaluate_event_for_agent_preserves_draft_status(
    agent_test_project: Project, db_session: Session
):
    # Create a draft conversational event
    event = ExecutionEvent(
        id="evt-safe-eval-1",
        project_id=agent_test_project.id,
        source_type="CONVERSATIONAL",
        reported_activity_code="CIV-1001",
        verbatim_excerpt="Poured 35 m3 for CIV-1001",
        description="Poured 35 m3 for CIV-1001",
        status="DRAFT",
        quantity=35.0,
        unit="m3",
        execution_date=datetime(2024, 10, 1),
    )
    db_session.add(event)
    db_session.commit()

    # Safe agent evaluation
    res = MatchingService.evaluate_event_for_agent(db=db_session, event=event)

    # Invariants:
    # 1. Status remains DRAFT
    assert event.status == "DRAFT"
    # 2. Matched activity is identified
    assert res.selected_candidate is not None
    assert res.selected_candidate.activity_id == "act-civ-1001"
    assert res.route == "AUTO_LINK"
    # 3. Top candidate score breakdown is available
    assert len(res.all_candidates) > 0
    top_cand = res.all_candidates[0]
    assert top_cand.activity_id == "act-civ-1001"
    assert top_cand.match_score >= 0.85

    # Check that the database event record still has status DRAFT
    db_session.expire_all()
    reloaded_event = db_session.query(ExecutionEvent).filter_by(id="evt-safe-eval-1").first()
    assert reloaded_event.status == "DRAFT"


# =========================================================================
# TEST SUITE D: Quantity Semantics & Schedule Update
# =========================================================================

def test_incremental_and_cumulative_quantity_semantics(
    agent_test_project: Project, db_session: Session
):
    act = db_session.query(Activity).filter_by(id="act-civ-1001").first()
    assert act.percent_complete == 0.0
    assert act.planned_quantity == 100.0

    # 1. Apply Incremental Progress: 35 m3 out of 100 m3 = 35%
    evt1 = ExecutionEvent(
        id="evt-quant-1",
        project_id=agent_test_project.id,
        matched_activity_id=act.id,
        verbatim_excerpt="Poured 35 m3",
        description="Poured 35 m3",
        status="APPROVED",
        quantity=35.0,
        unit="m3",
        execution_date=datetime(2024, 10, 1),
    )
    db_session.add(evt1)
    db_session.commit()

    res1 = ScheduleUpdateService.apply_event_progress(
        db=db_session,
        event_id=evt1.id,
        user_id="supervisor_test",
        quantity_semantics="INCREMENTAL",
        commit=True,
    )
    assert res1.percent_complete == 35.0
    assert res1.status == "IN_PROGRESS"

    # Verify ledger entry
    ledger1 = (
        db_session.query(ActualProgressLedger)
        .filter_by(execution_event_id=evt1.id)
        .first()
    )
    assert ledger1.installed_quantity == 35.0
    assert ledger1.incremental_percent == 35.0
    assert ledger1.cumulative_percent == 35.0

    # 2. Cumulative Progress: Report cumulative 60 m3 (delta = 60 - 35 = 25 m3 -> +25% = 60%)
    evt2 = ExecutionEvent(
        id="evt-quant-2",
        project_id=agent_test_project.id,
        matched_activity_id=act.id,
        verbatim_excerpt="Cumulative poured 60 m3",
        description="Cumulative poured 60 m3",
        status="APPROVED",
        quantity=60.0,
        unit="m3",
        execution_date=datetime(2024, 10, 2),
    )
    db_session.add(evt2)
    db_session.commit()

    res2 = ScheduleUpdateService.apply_event_progress(
        db=db_session,
        event_id=evt2.id,
        user_id="supervisor_test",
        quantity_semantics="CUMULATIVE",
        commit=True,
    )
    assert res2.percent_complete == 60.0

    # 3. Decreasing Cumulative Progress: Report cumulative 50 m3 (less than previous 60) -> REJECTED
    evt3 = ExecutionEvent(
        id="evt-quant-3",
        project_id=agent_test_project.id,
        matched_activity_id=act.id,
        verbatim_excerpt="Cumulative poured 50 m3",
        description="Cumulative poured 50 m3",
        status="APPROVED",
        quantity=50.0,
        unit="m3",
        execution_date=datetime(2024, 10, 3),
    )
    db_session.add(evt3)
    db_session.commit()

    with pytest.raises(ValidationException) as exc_info:
        ScheduleUpdateService.apply_event_progress(
            db=db_session,
            event_id=evt3.id,
            user_id="supervisor_test",
            quantity_semantics="CUMULATIVE",
            commit=True,
        )
    assert "cannot decrease progress" in str(exc_info.value)


# =========================================================================
# TEST SUITE E: Proposal Creation, Expiry, Baseline Conflict, and Confirmation
# =========================================================================

def test_proposal_lifecycle_and_conflict_handling(
    agent_test_project: Project, db_session: Session
):
    act = db_session.query(Activity).filter_by(id="act-str-2001").first()

    # Create conversation
    conv = Conversation(
        id="conv-prop-test",
        project_id=agent_test_project.id,
        user_id="lead_planner",
        status="ACTIVE",
    )
    db_session.add(conv)
    db_session.commit()

    # 1. Stage proposal: Update STR-2001 to 75%
    evt = ExecutionEvent(
        id="evt-prop-1",
        project_id=agent_test_project.id,
        conversation_id=conv.id,
        source_type="CONVERSATIONAL",
        reported_activity_code="STR-2001",
        verbatim_excerpt="Update STR-2001 to 75%",
        description="Update STR-2001 to 75%",
        status="DRAFT",
        execution_date=datetime(2024, 10, 1),
    )
    db_session.add(evt)
    db_session.commit()

    prop = TimeAgentService.stage_proposal(
        db=db_session,
        conversation=conv,
        event=evt,
        activity=act,
        proposed_percent=75.0,
        proposed_status="IN_PROGRESS",
        quantity_semantics="INCREMENTAL",
    )
    assert prop.status == "PENDING"
    assert prop.baseline_percent == 40.0
    assert prop.proposed_percent == 75.0
    assert prop.expires_at > datetime.utcnow()

    # 2. Confirm Proposal
    res_confirm = TimeAgentService.confirm_proposal(
        db=db_session,
        project_id=agent_test_project.id,
        conversation_id=conv.id,
        proposal_id=prop.id,
        caller_id="lead_planner",
    )
    assert res_confirm.status == "APPLIED"
    assert res_confirm.new_percent == 75.0
    assert res_confirm.activity_code == "STR-2001"

    # Proposal state must be CONSUMED
    db_session.expire_all()
    consumed_prop = db_session.query(UpdateProposal).filter_by(id=prop.id).first()
    assert consumed_prop.status == "CONSUMED"
    assert consumed_prop.consumed_at is not None

    # 3. Re-confirming an already consumed proposal raises 409
    with pytest.raises(Exception) as exc_con:
        TimeAgentService.confirm_proposal(
            db=db_session,
            project_id=agent_test_project.id,
            conversation_id=conv.id,
            proposal_id=prop.id,
            caller_id="lead_planner",
        )
    assert "PROPOSAL_ALREADY_CONSUMED" in str(exc_con.value) or "409" in str(exc_con.value)


def test_stale_proposal_conflict(agent_test_project: Project, db_session: Session):
    act = db_session.query(Activity).filter_by(id="act-civ-1001").first()

    conv = Conversation(
        id="conv-stale-test",
        project_id=agent_test_project.id,
        user_id="planner_1",
        status="ACTIVE",
    )
    db_session.add(conv)
    db_session.commit()

    evt = ExecutionEvent(
        id="evt-stale-1",
        project_id=agent_test_project.id,
        conversation_id=conv.id,
        source_type="CONVERSATIONAL",
        verbatim_excerpt="Update CIV-1001 to 50%",
        description="Update CIV-1001 to 50%",
        status="DRAFT",
        execution_date=datetime(2024, 10, 1),
    )
    db_session.add(evt)
    db_session.commit()

    prop = TimeAgentService.stage_proposal(
        db=db_session,
        conversation=conv,
        event=evt,
        activity=act,
        proposed_percent=50.0,
        proposed_status="IN_PROGRESS",
    )
    assert prop.baseline_percent == 0.0

    # Simulate concurrent external update to the activity percent
    act.percent_complete = 20.0
    db_session.commit()

    # Attempt confirmation -> must detect baseline mismatch (stale proposal)
    with pytest.raises(Exception) as exc_stale:
        TimeAgentService.confirm_proposal(
            db=db_session,
            project_id=agent_test_project.id,
            conversation_id=conv.id,
            proposal_id=prop.id,
            caller_id="planner_1",
        )
    assert "STALE_ACTIVITY_BASELINE" in str(exc_stale.value) or "409" in str(exc_stale.value)


# =========================================================================
# TEST SUITE F: End-to-End Conversational Flow & API Integration
# =========================================================================

def test_conversational_clarification_and_confirmation_flow(
    client: TestClient, agent_test_project: Project, db_session: Session
):
    project_id = agent_test_project.id

    # 1. Start a new conversation
    res = client.post(f"/api/v1/projects/{project_id}/agent/conversations")
    assert res.status_code == 200
    conv_data = res.json()
    conv_id = conv_data["conversation_id"]
    assert conv_data["project_id"] == project_id
    assert conv_data["status"] == "ACTIVE"

    # 2. Ambiguous report without exact activity: "We poured 35 m3 today."
    # Since both CIV-1001 and CIV-1002 are concrete pours, the system should generate clarification or matching candidates
    res_msg1 = client.post(
        f"/api/v1/projects/{project_id}/agent/conversations/{conv_id}/messages",
        json={"content": "We poured 35 m3 today."},
        headers={"X-User-ID": "supervisor_bob", "X-User-Role": "SUPERVISOR"},
    )
    assert res_msg1.status_code == 200
    resp1 = res_msg1.json()
    assert resp1["sender"] == "AGENT"
    assert resp1["action_card"] is not None

    # Check conversation active event is retained
    db_session.expire_all()
    conv = db_session.query(Conversation).filter_by(id=conv_id).first()
    assert conv.active_event_id is not None
    orig_event_id = conv.active_event_id

    # 3. Supervisor clarifies: "CIV-1001"
    res_msg2 = client.post(
        f"/api/v1/projects/{project_id}/agent/conversations/{conv_id}/messages",
        json={"content": "CIV-1001"},
        headers={"X-User-ID": "supervisor_bob", "X-User-Role": "SUPERVISOR"},
    )
    assert res_msg2.status_code == 200
    resp2 = res_msg2.json()

    # Same event should be enriched, not duplicated
    db_session.expire_all()
    conv = db_session.query(Conversation).filter_by(id=conv_id).first()
    assert conv.active_event_id == orig_event_id

    event = db_session.query(ExecutionEvent).filter_by(id=orig_event_id).first()
    assert event.reported_activity_code == "CIV-1001"

    # Proposal card should now be produced
    assert resp2["action_card"] is not None
    card = resp2["action_card"]
    print("DEBUG CARD:", card)
    assert card["type"] == "PROPOSAL_CONFIRMATION"
    assert card["activity_code"] == "CIV-1001"
    proposal_id = card["proposal_id"]
    assert proposal_id is not None

    # Verify activity in DB has NOT mutated yet (no unconfirmed write)
    db_session.expire_all()
    act = db_session.query(Activity).filter_by(id="act-civ-1001").first()
    assert act.percent_complete == 0.0

    # 4. Supervisor clicks [Confirm & Apply]
    res_conf = client.post(
        f"/api/v1/projects/{project_id}/agent/conversations/{conv_id}/confirm",
        json={"proposal_id": proposal_id},
        headers={"X-User-ID": "supervisor_bob", "X-User-Role": "SUPERVISOR"},
    )
    assert res_conf.status_code == 200
    conf_data = res_conf.json()
    assert conf_data["status"] == "APPLIED"
    assert conf_data["new_percent"] == 35.0
    assert conf_data["activity_code"] == "CIV-1001"

    # 5. Verify authoritative database mutations:
    db_session.expire_all()
    act_updated = db_session.query(Activity).filter_by(id="act-civ-1001").first()
    assert act_updated.percent_complete == 35.0
    assert act_updated.status == "IN_PROGRESS"
    assert act_updated.actual_start is not None

    # Verify ActualProgressLedger record
    ledger = (
        db_session.query(ActualProgressLedger)
        .filter_by(activity_id="act-civ-1001")
        .first()
    )
    assert ledger is not None
    assert ledger.installed_quantity == 35.0
    assert ledger.cumulative_percent == 35.0

    # Verify ScheduleAuditLog record
    audit = (
        db_session.query(ScheduleAuditLog)
        .filter_by(activity_id="act-civ-1001")
        .first()
    )
    assert audit is not None
    assert audit.user_id == "supervisor_bob"
    assert audit.action == "TIME_AGENT_CONVERSATIONAL_UPDATE"

    # Verify DomainOutbox event emitted
    outbox = (
        db_session.query(DomainOutbox)
        .filter_by(aggregate_id="act-civ-1001")
        .first()
    )
    assert outbox is not None
    assert outbox.event_type == "SCHEDULE_PROGRESS_UPDATED"


def test_gemini_credential_isolation(monkeypatch):
    """
    Verifies that Time Agent and Extraction Service can resolve credentials independently.
    """
    from app.services.agent_parser import ConversationalParser
    from app.services.extraction_service import ExtractionService

    # 1. Clear all keys
    monkeypatch.delenv("TIME_AGENT_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("EXTRACTION_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    p_none = ConversationalParser()
    assert p_none.gemini_api_key is None
    assert ExtractionService.extract_with_llm("test", "test.pdf") is None

    # 2. Configure Time Agent only
    monkeypatch.setenv("TIME_AGENT_GEMINI_API_KEY", "test-time-agent-key")
    p_time = ConversationalParser()
    assert p_time.gemini_api_key == "test-time-agent-key"
    # Extraction service remains None because it does not use TIME_AGENT_GEMINI_API_KEY
    assert ExtractionService.extract_with_llm("test", "test.pdf") is None

    # 3. Configure Extraction Service only
    monkeypatch.delenv("TIME_AGENT_GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("EXTRACTION_GEMINI_API_KEY", "test-extraction-key")
    p_none2 = ConversationalParser()
    assert p_none2.gemini_api_key is None

    # 4. Both configured independently
    monkeypatch.setenv("TIME_AGENT_GEMINI_API_KEY", "key-agent-123")
    monkeypatch.setenv("EXTRACTION_GEMINI_API_KEY", "key-extract-456")
    p_both = ConversationalParser()
    assert p_both.gemini_api_key == "key-agent-123"

    # 5. Shared fallback when dedicated keys are absent
    monkeypatch.delenv("TIME_AGENT_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("EXTRACTION_GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "shared-fallback-key")
    p_fallback = ConversationalParser()
    assert p_fallback.gemini_api_key == "shared-fallback-key"


def test_parse_with_gemini_prompt_formatting(monkeypatch):
    """
    Verifies that parse_with_gemini does not fail with ValueError due to unescaped f-string braces.
    """
    from app.services.agent_parser import ConversationalParser
    import httpx

    monkeypatch.setenv("TIME_AGENT_GEMINI_API_KEY", "dummy-api-key")

    def mock_post(url, *args, **kwargs):
        class MockResp:
            status_code = 200
            def json(self):
                return {
                    "candidates": [{
                        "content": {
                            "parts": [{
                                "text": '{"intent": "BULK_PROGRESS_REPORT", "is_bulk": true, "bulk_scope": {"discipline": "Electrical"}, "status_reported": "COMPLETED"}'
                            }]
                        }
                    }]
                }
        return MockResp()

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    parsed = ConversationalParser.parse_with_gemini(
        text="we have completed all the electrical activities update all of them",
        project_data_date_str="2024-09-30",
        active_activity_code=None,
        is_clarification_turn=False,
    )
    assert parsed is not None
    assert parsed.intent == "BULK_PROGRESS_REPORT"
    assert parsed.is_bulk is True
    assert parsed.bulk_scope == {"discipline": "Electrical"}


# =========================================================================
# TEST SUITE H: Schedule-Scoped Project Isolation & Chat History
# =========================================================================

def test_schedule_scoped_project_isolation_and_chat_history(
    client: TestClient, db_session: Session
):
    """
    Validates the 6 mandatory project-isolation criteria:
    Test 1: Project A conversations listing returns only A1, A2; Project B returns only B1.
    Test 2: Accessing Project B conversation via Project A URL path is rejected (404).
    Test 3: Search in Project A never returns Project B conversations.
    Test 4: Messages sent to Project A conversation remain attached to Project A.
    Test 5: Creating new conversation in Project A starts completely clean (no inherited messages).
    Test 6: New conversation in Project B has zero visibility of Project A messages.
    """
    # Setup Project A
    proj_a = Project(
        id="proj-alpha-iso",
        project_code="PROJECT_A",
        name="Schedule Alpha",
        planned_start=datetime(2024, 1, 1, 8, 0),
        planned_finish=datetime(2025, 12, 31, 17, 0),
        data_date=datetime(2024, 10, 1, 0, 0),
    )
    # Setup Project B
    proj_b = Project(
        id="proj-beta-iso",
        project_code="PROJECT_B",
        name="Schedule Beta",
        planned_start=datetime(2024, 1, 1, 8, 0),
        planned_finish=datetime(2025, 12, 31, 17, 0),
        data_date=datetime(2024, 10, 1, 0, 0),
    )
    db_session.add_all([proj_a, proj_b])
    db_session.commit()

    # Step 1: Create Conversation A1 in Project A
    res_a1 = client.post(
        f"/api/v1/projects/{proj_a.id}/agent/conversations",
        json={"force_new": True, "title": "F-204 Concrete Pour"},
    )
    assert res_a1.status_code == 200
    conv_a1 = res_a1.json()
    a1_id = conv_a1["conversation_id"]

    # Post message in A1
    msg_a1 = client.post(
        f"/api/v1/projects/{proj_a.id}/agent/conversations/{a1_id}/messages",
        json={"content": "We poured 35 m3 concrete for F-204 today."},
    )
    assert msg_a1.status_code == 200

    # Step 2: Create Conversation A2 in Project A
    res_a2 = client.post(
        f"/api/v1/projects/{proj_a.id}/agent/conversations",
        json={"force_new": True, "title": "Cable Tray Progress"},
    )
    assert res_a2.status_code == 200
    conv_a2 = res_a2.json()
    a2_id = conv_a2["conversation_id"]

    # Post message in A2
    msg_a2 = client.post(
        f"/api/v1/projects/{proj_a.id}/agent/conversations/{a2_id}/messages",
        json={"content": "Installed 18 meters of cable tray today."},
    )
    assert msg_a2.status_code == 200

    # Step 3: Create Conversation B1 in Project B
    res_b1 = client.post(
        f"/api/v1/projects/{proj_b.id}/agent/conversations",
        json={"force_new": True, "title": "Pump Installation"},
    )
    assert res_b1.status_code == 200
    conv_b1 = res_b1.json()
    b1_id = conv_b1["conversation_id"]

    # Post message in B1 (contains "pump")
    msg_b1 = client.post(
        f"/api/v1/projects/{proj_b.id}/agent/conversations/{b1_id}/messages",
        json={"content": "Installed centrifugal water pump today."},
    )
    assert msg_b1.status_code == 200

    # -------------------------------------------------------------
    # Test 1: GET Project A conversations -> only A1 and A2
    # -------------------------------------------------------------
    list_a = client.get(f"/api/v1/projects/{proj_a.id}/agent/conversations")
    assert list_a.status_code == 200
    items_a = list_a.json()
    ids_a = {item["id"] for item in items_a}
    assert ids_a == {a1_id, a2_id}
    assert b1_id not in ids_a

    list_b = client.get(f"/api/v1/projects/{proj_b.id}/agent/conversations")
    assert list_b.status_code == 200
    items_b = list_b.json()
    ids_b = {item["id"] for item in items_b}
    assert ids_b == {b1_id}
    assert a1_id not in ids_b
    assert a2_id not in ids_b

    # -------------------------------------------------------------
    # Test 2: Attempt to access Project B conversation via Project A path
    # -------------------------------------------------------------
    res_cross = client.get(f"/api/v1/projects/{proj_a.id}/agent/conversations/{b1_id}")
    assert res_cross.status_code == 404
    assert "not found in project" in res_cross.json()["detail"].lower()

    # -------------------------------------------------------------
    # Test 3: Search Project A for "pump" -> never returns Project B
    # -------------------------------------------------------------
    search_a_pump = client.get(f"/api/v1/projects/{proj_a.id}/agent/conversations?q=pump")
    assert search_a_pump.status_code == 200
    results_a_pump = search_a_pump.json()
    assert len(results_a_pump) == 0  # "pump" only exists in Project B!

    search_b_pump = client.get(f"/api/v1/projects/{proj_b.id}/agent/conversations?q=pump")
    assert search_b_pump.status_code == 200
    results_b_pump = search_b_pump.json()
    assert len(results_b_pump) == 1
    assert results_b_pump[0]["id"] == b1_id

    # Search Project A for "concrete" -> returns A1
    search_a_concrete = client.get(f"/api/v1/projects/{proj_a.id}/agent/conversations?q=concrete")
    assert search_a_concrete.status_code == 200
    results_a_concrete = search_a_concrete.json()
    assert any(item["id"] == a1_id for item in results_a_concrete)

    # -------------------------------------------------------------
    # Test 4: Open Project A conversation -> send message -> remains in A
    # -------------------------------------------------------------
    follow_up = client.post(
        f"/api/v1/projects/{proj_a.id}/agent/conversations/{a1_id}/messages",
        json={"content": "F-204 inspection completed."},
    )
    assert follow_up.status_code == 200
    get_a1 = client.get(f"/api/v1/projects/{proj_a.id}/agent/conversations/{a1_id}")
    assert get_a1.status_code == 200
    a1_history = get_a1.json()["history"]
    contents = [m["content"] for m in a1_history]
    assert any("F-204 inspection completed." in c for c in contents)

    # -------------------------------------------------------------
    # Test 5: Create new conversation in Project A -> starts clean
    # -------------------------------------------------------------
    res_a3 = client.post(
        f"/api/v1/projects/{proj_a.id}/agent/conversations",
        json={"force_new": True},
    )
    assert res_a3.status_code == 200
    conv_a3 = res_a3.json()
    assert conv_a3["history"] == []  # Completely clean, no messages inherited!
    assert conv_a3["active_event_id"] is None

    # -------------------------------------------------------------
    # Test 6: Check conversation in Project B -> no Project A messages visible
    # -------------------------------------------------------------
    get_b1 = client.get(f"/api/v1/projects/{proj_b.id}/agent/conversations/{b1_id}")
    assert get_b1.status_code == 200
    b1_history = get_b1.json()["history"]
    b1_contents = [m["content"] for m in b1_history]
    assert not any("F-204" in c for c in b1_contents)
    assert not any("cable tray" in c.lower() for c in b1_contents)


def test_deterministic_conversation_title_generation():
    """Validates deterministic 3-7 word conversation title generation."""
    # Pattern 1: Concrete Pour with tag
    t1 = TimeAgentService._generate_conversation_title(
        "We poured 35 m3 of concrete for F-204 today."
    )
    assert "F-204" in t1 and "Concrete" in t1

    # Pattern 2: Progress update with activity tag
    t2 = TimeAgentService._generate_conversation_title(
        "Update cable tray CT-07 to 80%."
    )
    assert "CT-07" in t2

    # Pattern 3: Information query
    t3 = TimeAgentService._generate_conversation_title(
        "Show upcoming civil activities."
    )
    assert "Upcoming Civil Activities" in t3

    # Pattern 4: Pump Installation
    t4 = TimeAgentService._generate_conversation_title(
        "Installed water pump today."
    )
    assert "Pump Installation" in t4


# =========================================================================
# TEST SUITE H: Dynamic Multi-Choice Clarification & Explicit Bulk Intent
# =========================================================================

def test_dynamic_clarification_two_candidates_preserves_ab_and_none_of_these(
    client: TestClient, agent_test_project: Project, db_session: Session
):
    """
    Validates that when exactly 2 candidates compete with close scores,
    the agent preserves the clean A/B comparison question and appends 'None of these'.
    """
    res_conv = client.post(
        f"/api/v1/projects/{agent_test_project.id}/agent/conversations",
        json={"force_new": True},
    )
    conv_id = res_conv.json()["conversation_id"]

    res_msg = client.post(
        f"/api/v1/projects/{agent_test_project.id}/agent/conversations/{conv_id}/messages",
        json={"content": "We completed the foundation work today."},
    )
    assert res_msg.status_code == 200
    data = res_msg.json()

    # Should ask A/B question
    reply = data["reply_text"]
    assert "CIV-1001" in reply or "CIV-1002" in reply
    assert "or" in reply

    card = data["action_card"]
    assert card is not None
    assert card["type"] == "CLARIFICATION_CHOICE"
    options = card["options"]
    assert len(options) == 3  # Candidate 1, Candidate 2, and None of these
    labels = [o["label"] for o in options]
    values = [o["value"] for o in options]
    assert any("CIV-1001" in l for l in labels)
    assert any("CIV-1002" in l for l in labels)
    assert "NONE_OF_THESE" in values


def test_dynamic_clarification_multi_candidates_and_none_of_these(
    client: TestClient, agent_test_project: Project, db_session: Session
):
    """
    Validates that when 3-4 candidates compete, the agent switches to
    a multi-choice clarification card with up to 4 candidates plus 'None of these'.
    """
    act3 = Activity(
        id="act-civ-1003",
        project_id=agent_test_project.id,
        wbs_id="wbs-agent-1",
        activity_code="CIV-1003",
        name="Foundation Concrete Pour F-206",
        status="NOT_STARTED",
        percent_complete=0.0,
    )
    act4 = Activity(
        id="act-civ-1004",
        project_id=agent_test_project.id,
        wbs_id="wbs-agent-1",
        activity_code="CIV-1004",
        name="Foundation Concrete Pour F-207",
        status="NOT_STARTED",
        percent_complete=0.0,
    )
    db_session.add_all([act3, act4])
    db_session.commit()

    res_conv = client.post(
        f"/api/v1/projects/{agent_test_project.id}/agent/conversations",
        json={"force_new": True},
    )
    conv_id = res_conv.json()["conversation_id"]

    res_msg = client.post(
        f"/api/v1/projects/{agent_test_project.id}/agent/conversations/{conv_id}/messages",
        json={"content": "We poured foundation concrete today."},
    )
    assert res_msg.status_code == 200
    data = res_msg.json()

    card = data["action_card"]
    assert card is not None
    assert card["type"] == "CLARIFICATION_CHOICE"
    options = card["options"]
    assert len(options) >= 4  # 3 or 4 candidates + None of these
    values = [o["value"] for o in options]
    assert "NONE_OF_THESE" in values
    assert "Select the activity" in data["reply_text"] or "possible activities" in data["reply_text"]


def test_clarification_none_of_these_handling(
    client: TestClient, agent_test_project: Project, db_session: Session
):
    """
    Validates that selecting 'None of these' prompts the user to provide an explicit code.
    """
    res_conv = client.post(
        f"/api/v1/projects/{agent_test_project.id}/agent/conversations",
        json={"force_new": True},
    )
    conv_id = res_conv.json()["conversation_id"]

    # Trigger clarification
    client.post(
        f"/api/v1/projects/{agent_test_project.id}/agent/conversations/{conv_id}/messages",
        json={"content": "We completed foundation work."},
    )

    # Respond with None of these
    res_none = client.post(
        f"/api/v1/projects/{agent_test_project.id}/agent/conversations/{conv_id}/messages",
        json={"content": "None of these"},
    )
    assert res_none.status_code == 200
    reply = res_none.json()["reply_text"]
    assert "specify" in reply.lower() and "activity code" in reply.lower()


def test_bulk_intent_detection_and_scoped_proposal_presentation(
    client: TestClient, agent_test_project: Project, db_session: Session
):
    """
    Validates that 'we have completed all the electrical activities update all of them':
    1. Extracts BULK_PROGRESS_REPORT intent.
    2. Queries authoritative DB for matching activities (does not let LLM hallucinate).
    3. Presents a BULK_SCOPE_PROPOSAL action card with total count and update button.
    """
    # Create 3 electrical activities in the project
    ele1 = Activity(
        id="act-ele-1001",
        project_id=agent_test_project.id,
        activity_code="ELE-1001",
        name="Cable Tray Installation Level 1",
        discipline="Electrical",
        status="NOT_STARTED",
        percent_complete=0.0,
    )
    ele2 = Activity(
        id="act-ele-1002",
        project_id=agent_test_project.id,
        activity_code="ELE-1002",
        name="Cable Tray Installation Level 2",
        discipline="Electrical",
        status="NOT_STARTED",
        percent_complete=0.0,
    )
    ele3 = Activity(
        id="act-ele-1003",
        project_id=agent_test_project.id,
        activity_code="ELE-1003",
        name="Main Switchgear Wiring",
        discipline="Electrical",
        status="NOT_STARTED",
        percent_complete=0.0,
    )
    db_session.add_all([ele1, ele2, ele3])
    db_session.commit()

    res_conv = client.post(
        f"/api/v1/projects/{agent_test_project.id}/agent/conversations",
        json={"force_new": True},
    )
    conv_id = res_conv.json()["conversation_id"]

    res_msg = client.post(
        f"/api/v1/projects/{agent_test_project.id}/agent/conversations/{conv_id}/messages",
        json={"content": "we have completed all the electrical activities update all of them"},
    )
    assert res_msg.status_code == 200
    data = res_msg.json()

    # Agent should identify all 3 activities and present a BULK_SCOPE_PROPOSAL card
    card = data["action_card"]
    assert card is not None
    assert card["type"] == "BULK_SCOPE_PROPOSAL"
    assert card["bulk_count"] == 3
    assert len(card["bulk_activities"]) == 3
    act_codes = [a["activity_code"] for a in card["bulk_activities"]]
    assert "ELE-1001" in act_codes
    assert "ELE-1002" in act_codes
    assert "ELE-1003" in act_codes

    # Options should have CONFIRM_ALL_BULK
    values = [o["value"] for o in card["options"]]
    assert "CONFIRM_ALL_BULK" in values
    assert "Cancel" in [o["label"] for o in card["options"]]


def test_clarification_turn_all_of_them_interception(
    client: TestClient, agent_test_project: Project, db_session: Session
):
    """
    Validates that when the agent asks a clarification question between activities,
    and the user replies 'all of them' or 'update all of them',
    the agent intercepts this and transitions to the bulk scope workflow instead of looping!
    """
    res_conv = client.post(
        f"/api/v1/projects/{agent_test_project.id}/agent/conversations",
        json={"force_new": True},
    )
    conv_id = res_conv.json()["conversation_id"]

    # Trigger clarification between civil foundation activities
    res1 = client.post(
        f"/api/v1/projects/{agent_test_project.id}/agent/conversations/{conv_id}/messages",
        json={"content": "Foundation pour completed."},
    )
    assert res1.json()["action_card"]["type"] == "CLARIFICATION_CHOICE"

    # Supervisor responds 'update all of them'
    res_bulk = client.post(
        f"/api/v1/projects/{agent_test_project.id}/agent/conversations/{conv_id}/messages",
        json={"content": "update all of them"},
    )
    assert res_bulk.status_code == 200
    data_bulk = res_bulk.json()

    # Must NOT re-ask between 2 choices! Must transition to BULK_SCOPE_PROPOSAL
    card = data_bulk["action_card"]
    assert card is not None
    assert card["type"] == "BULK_SCOPE_PROPOSAL"
    assert card["bulk_count"] >= 2


def test_bulk_proposal_confirmation_executes_atomic_schedule_mutation(
    client: TestClient, agent_test_project: Project, db_session: Session
):
    """
    Validates that confirming a bulk proposal transactionally mutates each activity in the database,
    creates actual progress ledger records, and creates schedule audit logs in a single atomic commit.
    """
    act_a = db_session.query(Activity).filter_by(id="act-civ-1001").first()
    act_b = db_session.query(Activity).filter_by(id="act-civ-1002").first()
    assert act_a.percent_complete == 0.0
    assert act_b.percent_complete == 0.0

    res_conv = client.post(
        f"/api/v1/projects/{agent_test_project.id}/agent/conversations",
        json={"force_new": True},
    )
    conv_id = res_conv.json()["conversation_id"]

    # Confirm bulk update for both activities to 100%
    res_confirm = client.post(
        f"/api/v1/projects/{agent_test_project.id}/agent/conversations/{conv_id}/bulk-confirm",
        json={
            "activity_ids": ["act-civ-1001", "act-civ-1002"],
            "action": "CONFIRM",
            "target_percent": 100.0,
            "status_reported": "COMPLETED",
        },
    )
    assert res_confirm.status_code == 200
    confirm_data = res_confirm.json()
    assert confirm_data["status"] == "APPLIED"
    assert confirm_data["updated_count"] == 2

    # Verify both activities in DB are updated
    db_session.refresh(act_a)
    db_session.refresh(act_b)
    assert act_a.percent_complete == 100.0
    assert act_a.status == "COMPLETED"
    assert act_b.percent_complete == 100.0
    assert act_b.status == "COMPLETED"

    # Verify ledger entries created
    ledgers_a = db_session.query(ActualProgressLedger).filter_by(activity_id="act-civ-1001").all()
    ledgers_b = db_session.query(ActualProgressLedger).filter_by(activity_id="act-civ-1002").all()
    assert len(ledgers_a) >= 1
    assert len(ledgers_b) >= 1
    assert ledgers_a[0].cumulative_percent == 100.0
    assert ledgers_b[0].cumulative_percent == 100.0

    # Verify audit logs created with TIME_AGENT_BULK_UPDATE action
    audits = db_session.query(ScheduleAuditLog).filter_by(project_id=agent_test_project.id).all()
    bulk_audits = [a for a in audits if a.action == "TIME_AGENT_BULK_UPDATE"]
    assert len(bulk_audits) >= 2

