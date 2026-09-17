from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


VALID_RELATIONSHIP_TYPES = {"FS", "SS", "FF", "SF"}


class RelationshipBase(BaseModel):
    relationship_type: str = Field("FS", description="FS, SS, FF, SF")
    lag: float = Field(0.0, description="Lag in days")

    @field_validator("relationship_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        v_upper = v.upper()
        if v_upper not in VALID_RELATIONSHIP_TYPES:
            raise ValueError(f"Invalid relationship type '{v}'. Must be one of: {', '.join(VALID_RELATIONSHIP_TYPES)}")
        return v_upper


class RelationshipCreate(RelationshipBase):
    predecessor_id: str = Field(..., description="UUID of predecessor activity")
    successor_id: str = Field(..., description="UUID of successor activity")


class RelationshipUpdate(BaseModel):
    relationship_type: Optional[str] = None
    lag: Optional[float] = None

    @field_validator("relationship_type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_upper = v.upper()
            if v_upper not in VALID_RELATIONSHIP_TYPES:
                raise ValueError(f"Invalid relationship type '{v}'. Must be one of: {', '.join(VALID_RELATIONSHIP_TYPES)}")
            return v_upper
        return v


class RelationshipResponse(RelationshipBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    predecessor_id: str
    successor_id: str
    predecessor_code: Optional[str] = None
    predecessor_name: Optional[str] = None
    successor_code: Optional[str] = None
    successor_name: Optional[str] = None
    created_at: datetime
