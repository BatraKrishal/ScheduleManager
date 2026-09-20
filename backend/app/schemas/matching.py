from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class MatchCandidateDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    activity_id: str
    activity_code: str
    activity_name: str
    wbs_code: Optional[str] = None
    match_score: float
    margin_delta: float
    score_breakdown: Dict[str, Any] = {}


class ConfidenceRoutingResultDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    artifact_id: str
    route: str  # "AUTO_LINK", "PLANNER_REVIEW", "UNMATCHED"
    selected_candidate: Optional[MatchCandidateDTO] = None
    all_candidates: List[MatchCandidateDTO] = []


class MatchingEvaluationRequest(BaseModel):
    project_id: str
    event_ids: Optional[List[str]] = None


class MatchingEvaluationResponse(BaseModel):
    evaluated_count: int
    auto_linked_count: int
    review_queued_count: int
    unmatched_count: int
    results: List[ConfidenceRoutingResultDTO]
