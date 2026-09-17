import pytest
from app.domain.models import Activity, Project, WBSNode

def seed_project(db_session):
    proj = Project(
        id="proj-123",
        project_code="TEST-PROJ",
        name="Test Project",
    )
    wbs = WBSNode(
        id="wbs-123",
        project_id="proj-123",
        code="WBS-01",
        name="Engineering",
    )
    act1 = Activity(
        id="act-1",
        project_id="proj-123",
        wbs_id="wbs-123",
        activity_code="ACT-01",
        name="Foundation",
        status="COMPLETED",
        percent_complete=100.0,
        original_duration=10.0,
    )
    act2 = Activity(
        id="act-2",
        project_id="proj-123",
        wbs_id="wbs-123",
        activity_code="ACT-02",
        name="Framing",
        status="NOT_STARTED",
        percent_complete=0.0,
        original_duration=15.0,
    )
    db_session.add_all([proj, wbs, act1, act2])
    db_session.commit()
    return proj, wbs, act1, act2

def test_list_activities_with_filtering(client, db_session):
    seed_project(db_session)

    # All activities
    res = client.get("/projects/proj-123/activities")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # Filter by status
    res = client.get("/projects/proj-123/activities?status=COMPLETED")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["activity_code"] == "ACT-01"

    # Filter by activity_code search
    res = client.get("/projects/proj-123/activities?activity_code=ACT-02")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Framing"

def test_update_activity_patch(client, db_session):
    seed_project(db_session)

    # Patch percent complete and status
    patch_payload = {
        "status": "IN_PROGRESS",
        "percent_complete": 55.5,
        "name": "Updated Foundation Name",
    }
    res = client.patch("/activities/act-1", json=patch_payload)
    assert res.status_code == 200
    updated = res.json()
    assert updated["status"] == "IN_PROGRESS"
    assert updated["percent_complete"] == 55.5
    assert updated["name"] == "Updated Foundation Name"

    # Verify invalid percent complete rejection
    invalid_patch = {"percent_complete": 150.0}
    res_err = client.patch("/activities/act-1", json=invalid_patch)
    assert res_err.status_code == 422
