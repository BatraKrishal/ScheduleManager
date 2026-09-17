import pytest
from app.services.validation_service import ValidationService

def test_validation_missing_project_meta():
    schedule = {
        "project": {"project_code": "", "name": ""},
        "wbs": [],
        "activities": [],
        "relationships": [],
    }
    errors = ValidationService.validate_canonical_schedule(schedule)
    error_codes = {e.code for e in errors}
    assert "REQUIRED_PROJECT_CODE" in error_codes
    assert "REQUIRED_PROJECT_NAME" in error_codes

def test_validation_duplicate_activity_codes():
    schedule = {
        "project": {"project_code": "PROJ-1", "name": "Project 1"},
        "wbs": [],
        "activities": [
            {"activity_code": "ACT-101", "name": "Task 1", "status": "NOT_STARTED"},
            {"activity_code": "ACT-101", "name": "Duplicate Task", "status": "NOT_STARTED"},
        ],
        "relationships": [],
    }
    errors = ValidationService.validate_canonical_schedule(schedule)
    error_codes = {e.code for e in errors}
    assert "DUPLICATE_ACTIVITY_CODE" in error_codes

def test_validation_finish_before_start():
    schedule = {
        "project": {"project_code": "PROJ-1", "name": "Project 1"},
        "wbs": [],
        "activities": [
            {
                "activity_code": "ACT-101",
                "name": "Task 1",
                "status": "NOT_STARTED",
                "planned_start": "2024-05-10T08:00:00",
                "planned_finish": "2024-05-01T17:00:00",  # earlier than start
            }
        ],
        "relationships": [],
    }
    errors = ValidationService.validate_canonical_schedule(schedule)
    error_codes = {e.code for e in errors}
    assert "FINISH_BEFORE_START" in error_codes

def test_validation_missing_wbs_reference():
    schedule = {
        "project": {"project_code": "PROJ-1", "name": "Project 1"},
        "wbs": [{"code": "WBS-CIVIL", "name": "Civil"}],
        "activities": [
            {
                "activity_code": "ACT-101",
                "name": "Task 1",
                "wbs_code": "WBS-NONEXISTENT",
                "status": "NOT_STARTED",
            }
        ],
        "relationships": [],
    }
    errors = ValidationService.validate_canonical_schedule(schedule)
    error_codes = {e.code for e in errors}
    assert "INVALID_WBS_REFERENCE" in error_codes

def test_validation_self_referencing_relationship():
    schedule = {
        "project": {"project_code": "PROJ-1", "name": "Project 1"},
        "wbs": [],
        "activities": [
            {"activity_code": "ACT-101", "name": "Task 1", "status": "NOT_STARTED"}
        ],
        "relationships": [
            {
                "predecessor_code": "ACT-101",
                "successor_code": "ACT-101",
                "relationship_type": "FS",
            }
        ],
    }
    errors = ValidationService.validate_canonical_schedule(schedule)
    error_codes = {e.code for e in errors}
    assert "SELF_REFERENCING_RELATIONSHIP" in error_codes
