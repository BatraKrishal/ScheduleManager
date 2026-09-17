from __future__ import annotations

from typing import Dict, List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.models import Activity, WBSNode
from app.schemas.wbs import WBSNodeResponse, WBSTreeNode


class WBSRepository:
    @staticmethod
    def get_by_project(db: Session, project_id: str) -> List[WBSNodeResponse]:
        nodes = db.query(WBSNode).filter(WBSNode.project_id == project_id).order_by(WBSNode.code.asc()).all()
        results = []
        for n in nodes:
            count = db.query(func.count(Activity.id)).filter(Activity.wbs_id == n.id).scalar() or 0
            results.append(
                WBSNodeResponse(
                    id=n.id,
                    project_id=n.project_id,
                    parent_id=n.parent_id,
                    code=n.code,
                    name=n.name,
                    created_at=n.created_at,
                    activity_count=count,
                )
            )
        return results

    @staticmethod
    def get_by_id(db: Session, wbs_id: str) -> Optional[WBSNode]:
        return db.query(WBSNode).filter(WBSNode.id == wbs_id).first()

    @staticmethod
    def get_tree(db: Session, project_id: str) -> List[WBSTreeNode]:
        nodes = db.query(WBSNode).filter(WBSNode.project_id == project_id).order_by(WBSNode.code.asc()).all()
        if not nodes:
            return []

        # Count activities per WBS
        counts: Dict[str, int] = {}
        for n in nodes:
            c = db.query(func.count(Activity.id)).filter(Activity.wbs_id == n.id).scalar() or 0
            counts[n.id] = c

        # Build tree nodes dict
        tree_map: Dict[str, WBSTreeNode] = {}
        for n in nodes:
            tree_map[n.id] = WBSTreeNode(
                id=n.id,
                code=n.code,
                name=n.name,
                parent_id=n.parent_id,
                activity_count=counts.get(n.id, 0),
                children=[],
            )

        root_nodes: List[WBSTreeNode] = []
        for n in nodes:
            tree_node = tree_map[n.id]
            if n.parent_id and n.parent_id in tree_map:
                tree_map[n.parent_id].children.append(tree_node)
            else:
                root_nodes.append(tree_node)

        return root_nodes
