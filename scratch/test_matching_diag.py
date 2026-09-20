import os
import sys
from datetime import datetime

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.domain.database import Base
from app.domain.models import Project, WBSNode, Activity, ExecutionEvent
from app.services.matching_service import MatchingService

engine = create_engine("sqlite:///:memory:", echo=False)
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
db = Session()

proj = Project(
    id="p1",
    project_code="BOROUGE4_DEMO",
    name="Borouge 4 Petrochemical Expansion",
    data_date=datetime(2024, 6, 1, 8, 0, 0)
)
db.add(proj)

wbs = WBSNode(id="w1", project_id="p1", code="WBS-CIV", name="Civil Works")
db.add(wbs)

act1 = Activity(
    id="a1",
    project_id="p1",
    wbs_id="w1",
    activity_code="CIV-1001",
    name="Foundation Concrete Pour F-204",
    status="NOT_STARTED",
    percent_complete=0.0,
    planned_quantity=140.0,
    quantity_unit="m3",
    planned_start=datetime(2024, 5, 15, 8, 0, 0),
    planned_finish=datetime(2024, 6, 15, 17, 0, 0)
)
act2 = Activity(
    id="a2",
    project_id="p1",
    wbs_id="w1",
    activity_code="CIV-1002",
    name="Foundation Concrete Pour F-205",
    status="NOT_STARTED",
    percent_complete=0.0,
    planned_quantity=120.0,
    quantity_unit="m3",
    planned_start=datetime(2024, 6, 2, 8, 0, 0),
    planned_finish=datetime(2024, 6, 20, 17, 0, 0)
)
db.add_all([act1, act2])
db.commit()

# Test 1: Ambiguous event (Turn 1)
ev1 = ExecutionEvent(
    id="ev1",
    project_id="p1",
    verbatim_excerpt="We poured 35 cubic meters of concrete today.",
    description="We poured 35 cubic meters of concrete today.",
    execution_date=datetime(2024, 6, 1, 8, 0, 0),
    quantity=35.0,
    unit="m3",
    discipline="Civil"
)
db.add(ev1)
db.commit()

res1 = MatchingService.evaluate_event_for_agent(db, ev1)
print("=== TURN 1 EVALUATION ===")
print("Route:", res1.route)
for c in res1.all_candidates:
    print(f"  {c.activity_code}: match_score={c.match_score}, breakdown={c.score_breakdown}")

# Test 2: Enriched event (Turn 2 with F-204)
ev1.location = "F-204"
ev1.description = "We poured 35 cubic meters of concrete today. F-204."
ev1.verbatim_excerpt = "We poured 35 cubic meters of concrete today. F-204."
db.commit()

res2 = MatchingService.evaluate_event_for_agent(db, ev1)
print("\n=== TURN 2 EVALUATION (Enriched with F-204) ===")
print("Route:", res2.route)
print("Selected candidate:", res2.selected_candidate.activity_code if res2.selected_candidate else "None")
for c in res2.all_candidates:
    print(f"  {c.activity_code}: match_score={c.match_score}, breakdown={c.score_breakdown}")
