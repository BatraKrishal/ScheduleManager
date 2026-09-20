import os
import sys
from datetime import datetime
from uuid import uuid4

# Ensure backend directory is in sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.domain.database import Base
from app.domain.models import (
    Project, WBSNode, Activity, ExecutionEvent,
    Conversation, ConversationMessage, UpdateProposal,
    ActualProgressLedger, ScheduleAuditLog, DomainOutbox
)
from app.services.agent_service import TimeAgentService
from app.schemas.agent import ProposalConfirmRequest

def run_borouge4_demo():
    print("=" * 70)
    print("BOROUGE 4 PETROCHEMICAL EXPANSION - TIME AGENT DEMO")
    print("=" * 70)

    # In-memory SQLite engine for demonstration test
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # 1. Setup Project & Baseline Activities
    project_id = str(uuid4())
    project = Project(
        id=project_id,
        project_code="BOROUGE4_DEMO",
        name="Borouge 4 Petrochemical Expansion",
        data_date=datetime(2024, 6, 1, 8, 0, 0),
        planned_start=datetime(2024, 1, 1, 8, 0, 0),
        planned_finish=datetime(2025, 12, 31, 17, 0, 0)
    )
    db.add(project)

    wbs1 = WBSNode(
        id=str(uuid4()),
        project_id=project_id,
        code="WBS-CIV",
        name="Civil Works"
    )
    db.add(wbs1)

    # Activity CIV-1001: Foundation F-204 (planned 140 m3)
    act1 = Activity(
        id=str(uuid4()),
        project_id=project_id,
        wbs_id=wbs1.id,
        activity_code="CIV-1001",
        name="Foundation Concrete Pour F-204",
        status="NOT_STARTED",
        percent_complete=0.0,
        planned_quantity=140.0,
        quantity_unit="m3",
        planned_start=datetime(2024, 5, 15, 8, 0, 0),
        planned_finish=datetime(2024, 6, 15, 17, 0, 0)
    )
    db.add(act1)

    # Activity CIV-1002: Foundation F-205 (0% complete, planned 120 m3)
    act2 = Activity(
        id=str(uuid4()),
        project_id=project_id,
        wbs_id=wbs1.id,
        activity_code="CIV-1002",
        name="Foundation Concrete Pour F-205",
        status="NOT_STARTED",
        percent_complete=0.0,
        planned_quantity=120.0,
        quantity_unit="m3",
        planned_start=datetime(2024, 6, 2, 8, 0, 0),
        planned_finish=datetime(2024, 6, 20, 17, 0, 0)
    )
    db.add(act2)
    db.commit()

    print(f"Project Initialized: {project.project_code} (ID: {project.id})")
    print(f"  Activity 1: {act1.activity_code} | {act1.name}")
    print(f"              Progress: {act1.percent_complete}% | Planned: {act1.planned_quantity} {act1.quantity_unit} | Status: {act1.status}")
    print(f"  Activity 2: {act2.activity_code} | {act2.name}")
    print(f"              Progress: {act2.percent_complete}% | Planned: {act2.planned_quantity} {act2.quantity_unit} | Status: {act2.status}")
    print()

    # 2. Conversation Start
    conv = TimeAgentService.get_or_create_conversation(db, project_id=project_id, user_id="supervisor-salem")
    print(f"[CONVERSATION INITIATED]")
    print(f"  Conversation ID: {conv.conversation_id}")
    print(f"  Project ID:      {conv.project_id}")
    print(f"  Status:          {conv.status}")
    print("-" * 70)

    # 3. Turn 1: Direct Ambiguous User Utterance (Missing Location/Activity)
    user_turn1 = "We poured 35 cubic meters of concrete today."
    print(f"SUPERVISOR: \"{user_turn1}\"")

    resp1 = TimeAgentService.process_message(
        db,
        project_id=project_id,
        conversation_id=conv.conversation_id,
        user_content=user_turn1,
        caller_id="supervisor-salem"
    )

    print(f"\nTIME AGENT: \"{resp1.reply_text}\"")
    print(f"  Action Card Type: {resp1.action_card.type if resp1.action_card else 'None'}")
    print(f"  Active Event ID:  {resp1.action_card.event_id if resp1.action_card else 'None'}")
    if resp1.action_card and resp1.action_card.options:
        print("  Retrieved Competing Candidates / Options:")
        for opt in resp1.action_card.options:
            print(f"    - [{opt.get('activity_code')}] {opt.get('activity_name')} (Score: {opt.get('confidence_score')})")
    print("-" * 70)

    # 4. Turn 2: Supervisor Clarification specifying Foundation F-204
    user_turn2 = "F-204."
    print(f"SUPERVISOR: \"{user_turn2}\"")

    resp2 = TimeAgentService.process_message(
        db,
        project_id=project_id,
        conversation_id=conv.conversation_id,
        user_content=user_turn2,
        caller_id="supervisor-salem"
    )

    print(f"\nTIME AGENT: \"{resp2.reply_text}\"")
    print(f"  Action Card Type: {resp2.action_card.type if resp2.action_card else 'None'}")
    print(f"  Target Activity:  {resp2.action_card.activity_code if resp2.action_card else 'N/A'}")
    print(f"  Proposal ID:      {resp2.action_card.proposal_id if resp2.action_card else 'N/A'}")
    
    if resp2.action_card and resp2.action_card.proposal_id:
        card = resp2.action_card
        print(f"  Proposal Staged:")
        print(f"    Target:            [{card.activity_code}] {card.activity_name}")
        print(f"    Progress Delta:    {card.current_percent}% -> {card.proposed_percent}%")
        print(f"    Quantity Delta:    +{card.incremental_quantity} {card.unit}")
        print(f"    Execution Date:    {card.execution_date}")
    print("-" * 70)

    assert resp2.action_card.proposal_id is not None, "Proposal should be staged!"
    proposal_id = resp2.action_card.proposal_id

    # Verify that database was NOT mutated before confirmation (CPM firewall & transaction safety)
    db.refresh(act1)
    print(f"[CPM FIREWALL CHECK BEFORE CONFIRM]")
    print(f"  Activity CIV-1001 percent_complete: {act1.percent_complete}% (Still untouched: 0.0%)")
    assert act1.percent_complete == 0.0

    # 5. Turn 3: User Clicks "Confirm & Apply"
    print("\nSUPERVISOR ACTION: Clicks [Confirm & Apply]")
    confirm_resp = TimeAgentService.confirm_proposal(
        db,
        project_id=project_id,
        conversation_id=conv.conversation_id,
        proposal_id=proposal_id,
        caller_id="supervisor-salem"
    )

    print(f"CONFIRMATION RESULT: {confirm_resp.status}")
    print(f"  Message:         {confirm_resp.message}")
    print(f"  Activity:        {confirm_resp.activity_code}")
    print(f"  Final Progress:  {confirm_resp.new_percent}%")
    print("-" * 70)

    # 6. Verify Direct Database State in PostgreSQL/SQLite
    db.refresh(act1)
    print("AUTHORITATIVE DATABASE STATE VERIFICATION:")
    print(f"  Activity Code:    {act1.activity_code}")
    print(f"  Activity Name:    {act1.name}")
    print(f"  Percent Complete: {act1.percent_complete}%")
    print(f"  Planned Quantity: {act1.planned_quantity} {act1.quantity_unit}")
    print(f"  Status:           {act1.status}")
    print(f"  Actual Start:     {act1.actual_start}")

    # Check ActualProgressLedger
    ledger = db.query(ActualProgressLedger).filter(ActualProgressLedger.activity_id == act1.id).order_by(ActualProgressLedger.created_at.desc()).first()
    print(f"\nACTUAL PROGRESS LEDGER ENTRY:")
    print(f"  Ledger ID:            {ledger.id}")
    print(f"  Installed Quantity:   {ledger.installed_quantity} {ledger.unit_of_measure}")
    print(f"  Incremental Percent:  {ledger.incremental_percent}%")
    print(f"  Cumulative Percent:   {ledger.cumulative_percent}%")
    print(f"  Execution Event ID:   {ledger.execution_event_id}")

    # Check ScheduleAuditLog
    audit = db.query(ScheduleAuditLog).filter(ScheduleAuditLog.activity_id == act1.id).order_by(ScheduleAuditLog.timestamp.desc()).first()
    print(f"\nSCHEDULE AUDIT LOG ENTRY:")
    print(f"  Audit ID:         {audit.id}")
    print(f"  Action:           {audit.action}")
    print(f"  Previous State:   {audit.previous_state}")
    print(f"  New State:        {audit.new_state}")
    print(f"  Actor / User:     {audit.user_id}")
    print(f"  Timestamp:        {audit.timestamp}")

    # Check DomainOutbox
    outbox = db.query(DomainOutbox).filter(DomainOutbox.aggregate_id == act1.id).order_by(DomainOutbox.created_at.desc()).first()
    print(f"\nDOMAIN OUTBOX EVENT:")
    print(f"  Outbox ID:      {outbox.id}")
    print(f"  Event Type:     {outbox.event_type}")
    print(f"  Status:         {outbox.status}")
    print(f"  Payload:        {outbox.payload}")

    # Check UpdateProposal status
    prop_record = db.query(UpdateProposal).filter(UpdateProposal.id == proposal_id).first()
    print(f"\nUPDATE PROPOSAL RECORD:")
    print(f"  Status:         {prop_record.status} (Expected: CONSUMED)")
    print(f"  Confirmed By:   {prop_record.confirmed_by}")
    print(f"  Confirmed At:   {prop_record.confirmed_at}")
    print(f"  Consumed At:    {prop_record.consumed_at}")

    # Mathematical Assertions:
    # act1 baseline = 0.0% (0 m3 of 140 m3)
    # incremental poured = 35 m3
    # incremental percent = (35 / 140) * 100 = 25.0%
    # final cumulative percent = 25.0%
    # final ledger installed quantity = 35.0 m3
    assert act1.percent_complete == 25.0, f"Expected 25.0%, got {act1.percent_complete}%"
    assert ledger.installed_quantity == 35.0, f"Expected 35.0, got {ledger.installed_quantity}"
    assert ledger is not None
    assert audit is not None
    assert outbox is not None
    assert prop_record.status == "CONSUMED"

    print("=" * 70)
    print("BOROUGE 4 DEMO VERIFICATION COMPLETED AND VALIDATED!")
    print("=" * 70)

if __name__ == "__main__":
    run_borouge4_demo()
