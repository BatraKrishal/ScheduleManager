from __future__ import annotations

import math
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.domain.database import get_db
from app.domain.models import Activity
from app.repositories.activity_repo import ActivityRepository
from app.repositories.project_repo import ProjectRepository
from app.repositories.wbs_repo import WBSRepository
from app.schemas.activity import (
    ActivityCreate,
    ActivityListResponse,
    ActivityResponse,
    ActivityUpdate,
)
from app.services.validation_service import ValidationService

router = APIRouter(tags=["Activities"])


@router.get(
    "/projects/{project_id}/activities",
    response_model=ActivityListResponse,
    summary="Get filtered, sorted, paginated activities for a project",
)
def get_project_activities(
    project_id: str,
    activity_code: Optional[str] = Query(None, description="Filter by activity code substring"),
    name: Optional[str] = Query(None, description="Filter by name substring"),
    wbs_id: Optional[str] = Query(None, description="Filter by WBS node UUID"),
    status_filter: Optional[str] = Query(None, alias="status", description="NOT_STARTED, IN_PROGRESS, COMPLETED"),
    start_date_from: Optional[datetime] = Query(None, description="Planned start >= date"),
    start_date_to: Optional[datetime] = Query(None, description="Planned start <= date"),
    finish_date_from: Optional[datetime] = Query(None, description="Planned finish >= date"),
    finish_date_to: Optional[datetime] = Query(None, description="Planned finish <= date"),
    percent_min: Optional[float] = Query(None, ge=0, le=100, description="Min percent complete"),
    percent_max: Optional[float] = Query(None, ge=0, le=100, description="Max percent complete"),
    sort_by: str = Query("activity_code", description="Field to sort by"),
    sort_dir: str = Query("asc", description="Sort direction: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
    db: Session = Depends(get_db),
):
    proj = ProjectRepository.get_by_id(db, project_id)
    if not proj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    items, total = ActivityRepository.filter_activities(
        db=db,
        project_id=project_id,
        activity_code=activity_code,
        name=name,
        wbs_id=wbs_id,
        status=status_filter,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
        finish_date_from=finish_date_from,
        finish_date_to=finish_date_to,
        percent_min=percent_min,
        percent_max=percent_max,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )

    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1

    return ActivityListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/activities/{activity_id}",
    response_model=ActivityResponse,
    summary="Get activity details by ID",
)
def get_activity(activity_id: str, db: Session = Depends(get_db)):
    act = ActivityRepository.get_by_id(db, activity_id)
    if not act:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found.")

    return ActivityResponse(
        id=act.id,
        project_id=act.project_id,
        wbs_id=act.wbs_id,
        wbs_code=act.wbs_node.code if act.wbs_node else None,
        wbs_name=act.wbs_node.name if act.wbs_node else None,
        activity_code=act.activity_code,
        name=act.name,
        activity_type=act.activity_type,
        status=act.status,
        planned_start=act.planned_start,
        planned_finish=act.planned_finish,
        actual_start=act.actual_start,
        actual_finish=act.actual_finish,
        original_duration=act.original_duration,
        remaining_duration=act.remaining_duration,
        percent_complete=act.percent_complete,
        calendar=act.calendar,
        created_at=act.created_at,
        updated_at=act.updated_at,
    )


@router.post(
    "/projects/{project_id}/activities",
    response_model=ActivityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new activity in a project",
)
def create_activity(
    project_id: str,
    payload: ActivityCreate,
    db: Session = Depends(get_db),
):
    proj = ProjectRepository.get_by_id(db, project_id)
    if not proj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    # Check duplicate code
    existing = ActivityRepository.get_by_code(db, project_id, payload.activity_code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Activity code '{payload.activity_code}' already exists in this project.",
        )

    # Check WBS
    if payload.wbs_id:
        wbs = WBSRepository.get_by_id(db, payload.wbs_id)
        if not wbs or wbs.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Referenced WBS node does not exist in this project.",
            )

    # Validate dates
    if payload.planned_start and payload.planned_finish and payload.planned_finish < payload.planned_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Planned finish date cannot precede planned start date.",
        )

    act = Activity(
        project_id=project_id,
        wbs_id=payload.wbs_id,
        activity_code=payload.activity_code,
        name=payload.name,
        activity_type=payload.activity_type or "TT_Task",
        status=(payload.status or "NOT_STARTED").upper(),
        planned_start=payload.planned_start,
        planned_finish=payload.planned_finish,
        actual_start=payload.actual_start,
        actual_finish=payload.actual_finish,
        original_duration=payload.original_duration,
        remaining_duration=payload.remaining_duration,
        percent_complete=payload.percent_complete or 0.0,
        calendar=payload.calendar,
    )
    db.add(act)
    db.commit()
    db.refresh(act)

    return get_activity(act.id, db)


@router.patch(
    "/activities/{activity_id}",
    response_model=ActivityResponse,
    summary="Update activity schedule data",
)
def update_activity(
    activity_id: str,
    payload: ActivityUpdate,
    db: Session = Depends(get_db),
):
    act = ActivityRepository.get_by_id(db, activity_id)
    if not act:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found.")

    updates = payload.model_dump(exclude_unset=True)

    # Validate updates
    ValidationService.validate_activity_update(
        updates=updates,
        current_start=act.planned_start,
        current_finish=act.planned_finish,
    )

    # Check WBS if provided
    if "wbs_id" in updates and updates["wbs_id"]:
        wbs = WBSRepository.get_by_id(db, updates["wbs_id"])
        if not wbs or wbs.project_id != act.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Referenced WBS node does not exist in this project.",
            )

    # Check unique activity code if changing code
    if "activity_code" in updates and updates["activity_code"] != act.activity_code:
        conflict = ActivityRepository.get_by_code(db, act.project_id, updates["activity_code"])
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Activity code '{updates['activity_code']}' already exists in this project.",
            )

    ActivityRepository.update(db, act, updates)
    db.commit()
    db.refresh(act)

    return get_activity(act.id, db)


@router.delete(
    "/activities/{activity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an activity",
)
def delete_activity(activity_id: str, db: Session = Depends(get_db)):
    deleted = ActivityRepository.delete(db, activity_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found.")
    return None
