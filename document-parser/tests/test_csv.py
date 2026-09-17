import pytest
from app.models.canonical import ActivityStatus, RelationshipType
from app.parsers.csv_parser import CsvParser

SAMPLE_CSV = """Activity ID,Activity Name,WBS,Status,Start,Finish,Duration,% Complete,Predecessors
TASK-01,Foundation Works,Civil,Completed,2024-01-05,2024-01-15,10,100,
TASK-02,Steel Framing,Structural,In Progress,2024-01-16,2024-02-05,20,50,TASK-01FS
TASK-03,Cladding,Facade,Not Started,2024-02-06,2024-02-20,14,0,TASK-02SS+2
"""

def test_parse_valid_csv():
    parser = CsvParser()
    result = parser.parse(SAMPLE_CSV.encode("utf-8"), "schedule.csv")

    assert result.project.project_code == "schedule"
    assert len(result.wbs) == 3
    wbs_codes = {w.code for w in result.wbs}
    assert "Civil" in wbs_codes
    assert "Structural" in wbs_codes
    assert "Facade" in wbs_codes

    assert len(result.activities) == 3
    assert result.activities[0].activity_code == "TASK-01"
    assert result.activities[0].status == ActivityStatus.COMPLETED
    assert result.activities[1].activity_code == "TASK-02"
    assert result.activities[1].status == ActivityStatus.IN_PROGRESS

    assert len(result.relationships) == 2
    r1 = result.relationships[0]
    assert r1.predecessor_code == "TASK-01"
    assert r1.successor_code == "TASK-02"
    assert r1.relationship_type == RelationshipType.FS

    r2 = result.relationships[1]
    assert r2.predecessor_code == "TASK-02"
    assert r2.successor_code == "TASK-03"
    assert r2.relationship_type == RelationshipType.SS
    assert r2.lag == 2.0
