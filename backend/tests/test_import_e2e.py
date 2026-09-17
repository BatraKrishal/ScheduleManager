import io
from unittest.mock import patch
import pytest
import httpx

MOCK_CANONICAL = {
    "project": {
        "project_code": "PROJ-E2E",
        "name": "E2E Construction Project",
        "planned_start": "2024-01-01T08:00:00",
        "planned_finish": "2024-12-31T17:00:00",
        "data_date": "2024-01-01T08:00:00",
    },
    "wbs": [
        {"code": "WBS-1", "name": "Civil Works", "parent_code": None},
        {"code": "WBS-1.1", "name": "Earthmoving", "parent_code": "WBS-1"},
    ],
    "activities": [
        {
            "activity_code": "ACT-101",
            "name": "Clearing and Grubbing",
            "wbs_code": "WBS-1.1",
            "activity_type": "TT_Task",
            "status": "COMPLETED",
            "planned_start": "2024-01-01T08:00:00",
            "planned_finish": "2024-01-10T17:00:00",
            "actual_start": "2024-01-01T08:00:00",
            "actual_finish": "2024-01-10T17:00:00",
            "original_duration": 10.0,
            "remaining_duration": 0.0,
            "percent_complete": 100.0,
        },
        {
            "activity_code": "ACT-102",
            "name": "Trenching",
            "wbs_code": "WBS-1.1",
            "activity_type": "TT_Task",
            "status": "IN_PROGRESS",
            "planned_start": "2024-01-11T08:00:00",
            "planned_finish": "2024-01-25T17:00:00",
            "actual_start": "2024-01-11T08:00:00",
            "actual_finish": None,
            "original_duration": 14.0,
            "remaining_duration": 7.0,
            "percent_complete": 50.0,
        },
    ],
    "relationships": [
        {
            "predecessor_code": "ACT-101",
            "successor_code": "ACT-102",
            "relationship_type": "FS",
            "lag": 0.0,
        }
    ],
}

def test_full_import_and_query_flow(client):
    # Mock httpx.AsyncClient.post to return MOCK_CANONICAL
    class MockResponse:
        status_code = 200
        def json(self):
            return MOCK_CANONICAL

    async def mock_post(*args, **kwargs):
        return MockResponse()

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        file_bytes = b"dummy file content"
        res = client.post(
            "/projects/import",
            files={"file": ("project.xer", io.BytesIO(file_bytes), "application/octet-stream")},
        )

    assert res.status_code == 201
    proj = res.json()
    assert proj["project_code"] == "PROJ-E2E"
    proj_id = proj["id"]

    # Verify WBS tree
    wbs_res = client.get(f"/projects/{proj_id}/wbs/tree")
    assert wbs_res.status_code == 200
    wbs_tree = wbs_res.json()
    assert len(wbs_tree) == 1
    assert wbs_tree[0]["code"] == "WBS-1"
    assert len(wbs_tree[0]["children"]) == 1
    assert wbs_tree[0]["children"][0]["code"] == "WBS-1.1"

    # Verify Activities list
    act_res = client.get(f"/projects/{proj_id}/activities")
    assert act_res.status_code == 200
    act_data = act_res.json()
    assert act_data["total"] == 2
    assert act_data["items"][0]["activity_code"] == "ACT-101"
    assert act_data["items"][1]["activity_code"] == "ACT-102"

    # Verify Relationships
    rel_res = client.get(f"/projects/{proj_id}/relationships")
    assert rel_res.status_code == 200
    rels = rel_res.json()
    assert len(rels) == 1
    assert rels[0]["predecessor_code"] == "ACT-101"
    assert rels[0]["successor_code"] == "ACT-102"
    assert rels[0]["relationship_type"] == "FS"
