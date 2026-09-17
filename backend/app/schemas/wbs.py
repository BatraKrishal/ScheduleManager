from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class WBSNodeBase(BaseModel):
    code: str = Field(..., description="WBS code")
    name: str = Field(..., description="WBS name")
    parent_id: Optional[str] = None


class WBSNodeCreate(WBSNodeBase):
    project_id: str


class WBSNodeResponse(WBSNodeBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    created_at: datetime
    activity_count: int = 0


class WBSTreeNode(BaseModel):
    id: str
    code: str
    name: str
    parent_id: Optional[str] = None
    activity_count: int = 0
    children: List[WBSTreeNode] = Field(default_factory=list)
