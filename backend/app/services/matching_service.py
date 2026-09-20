from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.domain.models import Activity, ExecutionEvent, WBSNode
from app.schemas.matching import ConfidenceRoutingResultDTO, MatchCandidateDTO

logger = logging.getLogger("matching_service")


class MatchingService:
    @staticmethod
    def _tokenize(text: str) -> set[str]:
        if not text:
            return set()
        clean = re.sub(r"[^\w\s]", " ", text.lower())
        tokens = {t for t in clean.split() if len(t) > 2}
        return tokens

    @classmethod
    def calculate_text_similarity(cls, text_a: str, text_b: str) -> float:
        """
        Calculates text alignment between event text (text_a) and activity name (text_b).
        Considers both token coverage (what fraction of activity name terms are mentioned)
        and token set Jaccard similarity.
        """
        tokens_a = cls._tokenize(text_a)
        tokens_b = cls._tokenize(text_b)
        if not tokens_a or not tokens_b:
            return 0.0

        # Substring / stem-tolerant token coverage of activity name (text_b)
        matched_b = 0
        for tb in tokens_b:
            if any(tb in ta or ta in tb for ta in tokens_a):
                matched_b += 1
        coverage = matched_b / len(tokens_b) if tokens_b else 0.0

        # Jaccard index
        intersection = tokens_a.intersection(tokens_b)
        union = tokens_a.union(tokens_b)
        jaccard = len(intersection) / len(union) if union else 0.0

        return round(0.75 * coverage + 0.25 * jaccard, 3)

    @classmethod
    def calculate_temporal_score(
        cls, event_date: datetime, planned_start: Optional[datetime], planned_finish: Optional[datetime]
    ) -> float:
        if not planned_start or not planned_finish:
            return 0.5  # Neutral when no planned dates exist

        # If event falls within planned interval
        if planned_start <= event_date <= planned_finish:
            return 1.0

        # Measure distance from planned window
        if event_date < planned_start:
            delta_days = (planned_start - event_date).days
        else:
            delta_days = (event_date - planned_finish).days

        if delta_days <= 7:
            return 0.8
        elif delta_days <= 14:
            return 0.6
        elif delta_days <= 30:
            return 0.4
        return 0.1

    @classmethod
    def score_activity(
        cls, event: ExecutionEvent, activity: Activity, wbs_node: Optional[WBSNode]
    ) -> Tuple[float, Dict[str, float]]:
        # 1. Exact ID / Code Signal (S_id)
        s_id = 0.0
        reported_code = (event.reported_activity_code or "").upper().strip()
        verbatim_upper = (event.verbatim_excerpt or "").upper()
        act_code = activity.activity_code.upper().strip()

        if reported_code and reported_code == act_code:
            s_id = 1.0
        elif act_code in verbatim_upper:
            s_id = 1.0

        # 2. Text & Token Similarity (S_text)
        s_text = cls.calculate_text_similarity(
            f"{event.description} {event.verbatim_excerpt} {event.activity_reference or ''}",
            activity.name,
        )

        # 3. WBS & Hierarchy Alignment (S_wbs)
        s_wbs = 0.0
        wbs_name = (wbs_node.name if wbs_node else "").lower()
        wbs_hint = (event.wbs_hint or "").lower()
        event_loc = (event.location or "").lower()

        if wbs_hint and wbs_name and (wbs_hint in wbs_name or wbs_name in wbs_hint):
            s_wbs = 1.0
        elif event_loc and wbs_name and any(term in wbs_name for term in event_loc.split()):
            s_wbs = 0.95
        elif activity.discipline and event.discipline:
            if activity.discipline.lower() in event.discipline.lower() or event.discipline.lower() in activity.discipline.lower():
                s_wbs = 0.85
        elif s_text >= 0.70:
            s_wbs = 0.90
        elif s_text > 0.4:
            s_wbs = 0.50

        # 4. Temporal Compatibility (S_temp)
        s_temp = cls.calculate_temporal_score(
            event.execution_date, activity.planned_start, activity.planned_finish
        )

        # 5. Contextual Alignment (S_context)
        s_context = 0.0
        if event.location:
            loc_lower = event.location.lower()
            if loc_lower in activity.name.lower() or (activity.location_code and loc_lower in activity.location_code.lower()):
                s_context = 1.0
        if event.contractor and activity.contractor_name:
            if event.contractor.lower() in activity.contractor_name.lower():
                s_context = min(1.0, s_context + 0.2)
            else:
                s_context = max(0.0, s_context - 0.2)

        # Weighted combination:
        # If exact activity code is present, S_total is guaranteed >= 0.95.
        # If activity code is not present, weights normalize across text, wbs, temporal, and contextual signals.
        if s_id == 1.0:
            s_total = max(0.95, 0.40 * s_id + 0.30 * s_text + 0.15 * s_wbs + 0.10 * s_temp + 0.05 * s_context)
        else:
            # Normalized weights when code is not cited in field narrative: 0.45 text, 0.25 wbs, 0.15 temp, 0.15 context
            s_total = (
                0.45 * s_text
                + 0.25 * s_wbs
                + 0.15 * s_temp
                + 0.15 * s_context
            )

        breakdown = {
            "s_id": round(s_id, 3),
            "s_text": round(s_text, 3),
            "s_wbs": round(s_wbs, 3),
            "s_temp": round(s_temp, 3),
            "s_context": round(s_context, 3),
            "s_total": round(s_total, 3),
        }
        return round(s_total, 3), breakdown

    @classmethod
    def retrieve_candidates(cls, db: Session, event: ExecutionEvent) -> List[Activity]:
        """SQL candidate retrieval: Active activities within project and optional temporal window."""
        query = db.query(Activity).filter(
            Activity.project_id == event.project_id,
            Activity.status != "COMPLETED",
        )

        activities = query.all()
        # If temporal window filtering produces candidates, prefer them; otherwise fallback to all active
        event_d = event.execution_date
        window_start = event_d - timedelta(days=30)
        window_end = event_d + timedelta(days=30)

        in_window = [
            a for a in activities
            if not a.planned_start or not a.planned_finish or (a.planned_start <= window_end and a.planned_finish >= window_start)
        ]
        return in_window if in_window else activities

    @classmethod
    def evaluate_event(cls, db: Session, event: ExecutionEvent) -> ConfidenceRoutingResultDTO:
        """
        Match an ExecutionEvent against project activities, compute match scores,
        evaluate margin delta, and route to AUTO_LINK or PLANNER_REVIEW.
        """
        candidates = cls.retrieve_candidates(db, event)
        if not candidates:
            event.status = "UNMATCHED"
            db.commit()
            return ConfidenceRoutingResultDTO(
                event_id=event.id,
                artifact_id=event.artifact_id,
                route="UNMATCHED",
                selected_candidate=None,
                all_candidates=[],
            )

        scored_candidates: List[MatchCandidateDTO] = []
        for act in candidates:
            wbs = db.query(WBSNode).filter(WBSNode.id == act.wbs_id).first() if act.wbs_id else None
            score, breakdown = cls.score_activity(event, act, wbs)
            scored_candidates.append(
                MatchCandidateDTO(
                    activity_id=act.id,
                    activity_code=act.activity_code,
                    activity_name=act.name,
                    wbs_code=wbs.code if wbs else None,
                    match_score=score,
                    margin_delta=0.0,
                    score_breakdown=breakdown,
                )
            )

        scored_candidates.sort(key=lambda x: x.match_score, reverse=True)

        # Calculate margin delta between top and second candidate
        top = scored_candidates[0]
        if len(scored_candidates) > 1:
            second = scored_candidates[1]
            margin_delta = round(top.match_score - second.match_score, 3)
        else:
            margin_delta = top.match_score

        top.margin_delta = margin_delta

        # Confidence routing rule per doc Section 13:
        # S_total >= 0.85 AND margin_delta >= 0.15 AND extraction_confidence >= 0.80
        is_auto_link = (
            top.match_score >= 0.85
            and margin_delta >= 0.15
            and event.extraction_confidence >= 0.80
        )

        route = "AUTO_LINK" if is_auto_link else "PLANNER_REVIEW"

        event.matched_activity_id = top.activity_id
        event.match_score = top.match_score
        event.match_metadata = json.dumps({
            "route": route,
            "margin_delta": margin_delta,
            "top_candidate": top.model_dump(),
            "all_scored": [c.model_dump() for c in scored_candidates[:5]],
        })

        if route == "AUTO_LINK":
            event.status = "AUTO_LINKED"
        else:
            event.status = "IN_REVIEW"

        db.commit()

        return ConfidenceRoutingResultDTO(
            event_id=event.id,
            artifact_id=event.artifact_id,
            route=route,
            selected_candidate=top,
            all_candidates=scored_candidates[:5],
        )
