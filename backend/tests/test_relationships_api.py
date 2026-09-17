import pytest
from app.domain.models import Activity, Project

def seed_two_activities(db_session):
    proj = Project(id="proj-rel", project_code="REL-PROJ", name="Rel Test")
    act1 = Activity(id="act-a", project_id="proj-rel", activity_code="ACT-A", name="Task A")
    act2 = Activity(id="act-b", project_id="proj-rel", activity_code="ACT-B", name="Task B")
    db_session.add_all([proj, act1, act2])
    db_session.commit()

def test_create_relationship_success(client, db_session):
    seed_two_activities(db_session)

    payload = {
        "predecessor_id": "act-a",
        "successor_id": "act-b",
        "relationship_type": "FS",
        "lag": 2.5,
    }
    res = client.post("/projects/proj-rel/relationships", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["predecessor_code"] == "ACT-A"
    assert data["successor_code"] == "ACT-B"
    assert data["relationship_type"] == "FS"
    assert data["lag"] == 2.5

def test_prevent_self_referencing_relationship(client, db_session):
    seed_two_activities(db_session)

    payload = {
        "predecessor_id": "act-a",
        "successor_id": "act-a",
        "relationship_type": "FS",
    }
    res = client.post("/projects/proj-rel/relationships", json=payload)
    assert res.status_code == 400
    assert "relationship with itself" in res.json()["detail"]
