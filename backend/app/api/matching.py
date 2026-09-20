from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.domain.database import get_db
from app.domain.models import ExecutionEvent, Project
from app.schemas.matching import (
    MatchingEvaluationRequest,
    MatchingEvaluationResponse,
)
from app.services.matching_service import MatchingService
from app.services.schedule_update_service import ScheduleUpdateService

logger = logging.getLogger("matching_api")
router = APIRouter(tags=["Matching"])


@router.post(
    "/api/v1/matching/evaluate",
    response_model=MatchingEvaluationResponse,
)
def evaluate_matching(
    request: MatchingEvaluationRequest,
    db: Session = Depends(get_db),
):
    """
    Evaluate ExecutionEvents against project activities, compute match scores,
    execute confidence routing, and automatically link HIGH confidence matches.
    """
    project = db.query(Project).filter(Project.id == request.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {request.project_id} not found.",
        )

    query = db.query(ExecutionEvent).filter(
        ExecutionEvent.project_id == request.project_id,
        ExecutionEvent.status.in_(["UNMATCHED", "IN_REVIEW"]),
    )
    if request.event_ids:
        query = query.filter(ExecutionEvent.id.in_(request.event_ids))

    events = query.all()
    results = []
    auto_linked = 0
    review_queued = 0
    unmatched = 0

    for event in events:
        eval_result = MatchingService.evaluate_event(db, event)
        results.append(eval_result)

        if eval_result.route == "AUTO_LINK" and eval_result.selected_candidate:
            try:
                ScheduleUpdateService.apply_event_progress(
                    db=db,
                    event_id=event.id,
                    activity_id=eval_result.selected_candidate.activity_id,
                    user_id="system-auto",
                    action_name="AUTO_LINK_PROGRESS",
                )
                auto_linked += 1
            except Exception as e:
                logger.error(f"Failed to auto-link event {event.id}: {e}")
                review_queued += 1
        elif eval_result.route == "PLANNER_REVIEW":
            review_queued += 1
        else:
            unmatched += 1

    return MatchingEvaluationResponse(
        evaluated_count=len(events),
        auto_linked_count=auto_linked,
        review_queued_count=review_queued,
        unmatched_count=unmatched,
        results=results,
    )
