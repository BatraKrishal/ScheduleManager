from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.extraction import ExecutionEventDTO
from app.schemas.matching import MatchCandidateDTO


class ReviewDecisionRequest(BaseModel):
    event_id: str
    decision: str  # "APPROVED", "REJECTED", "REASSIGNED"
    activity_id: Optional[str] = None
    adjustment_percent: Optional[float] = None
    reviewer_id: str = "planner-user"
    notes: Optional[str] = None


class ReviewDecisionResponse(BaseModel):
    decision_id: str
    event_id: str
    status: str
    activity_id: Optional[str] = None
    applied_progress_percent: Optional[float] = None
    message: str


class ReviewQueueItemDTO(BaseModel):
    event: ExecutionEventDTO
    candidates: List[MatchCandidateDTO] = []
    artifact_view_url: Optional[str] = None


class ReviewQueueResponse(BaseModel):
    project_id: str
    pending_count: int
    items: List[ReviewQueueItemDTO]
