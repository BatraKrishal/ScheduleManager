from __future__ import annotations

from typing import Dict, List, Optional
from sqlalchemy.orm import Session, aliased

from app.domain.models import Activity, ActivityRelationship
from app.schemas.relationship import RelationshipResponse


class RelationshipRepository:
    @staticmethod
    def get_by_project(db: Session, project_id: str) -> List[RelationshipResponse]:
        pred_act = aliased(Activity)
        succ_act = aliased(Activity)

        rows = (
            db.query(ActivityRelationship, pred_act, succ_act)
            .join(pred_act, ActivityRelationship.predecessor_id == pred_act.id)
            .join(succ_act, ActivityRelationship.successor_id == succ_act.id)
            .filter(ActivityRelationship.project_id == project_id)
            .all()
        )

        results = []
        for rel, p, s in rows:
            results.append(
                RelationshipResponse(
                    id=rel.id,
                    project_id=rel.project_id,
                    predecessor_id=rel.predecessor_id,
                    successor_id=rel.successor_id,
                    predecessor_code=p.activity_code,
                    predecessor_name=p.name,
                    successor_code=s.activity_code,
                    successor_name=s.name,
                    relationship_type=rel.relationship_type,
                    lag=rel.lag,
                    created_at=rel.created_at,
                )
            )
        return results

    @staticmethod
    def get_by_id(db: Session, relationship_id: str) -> Optional[ActivityRelationship]:
        return db.query(ActivityRelationship).filter(ActivityRelationship.id == relationship_id).first()

    @staticmethod
    def create(db: Session, rel: ActivityRelationship) -> ActivityRelationship:
        db.add(rel)
        db.flush()
        return rel

    @staticmethod
    def update(db: Session, rel: ActivityRelationship, updates: Dict) -> ActivityRelationship:
        for field, val in updates.items():
            if hasattr(rel, field) and val is not None:
                setattr(rel, field, val)
        db.flush()
        return rel

    @staticmethod
    def delete(db: Session, relationship_id: str) -> bool:
        rel = db.query(ActivityRelationship).filter(ActivityRelationship.id == relationship_id).first()
        if not rel:
            return False
        db.delete(rel)
        db.commit()
        return True
