from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    planned_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    planned_finish: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    data_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    wbs_nodes: Mapped[List[WBSNode]] = relationship(
        "WBSNode", back_populates="project", cascade="all, delete-orphan"
    )
    activities: Mapped[List[Activity]] = relationship(
        "Activity", back_populates="project", cascade="all, delete-orphan"
    )
    relationships: Mapped[List[ActivityRelationship]] = relationship(
        "ActivityRelationship", back_populates="project", cascade="all, delete-orphan"
    )


class WBSNode(Base):
    __tablename__ = "wbs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("wbs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project: Mapped[Project] = relationship("Project", back_populates="wbs_nodes")
    parent: Mapped[Optional[WBSNode]] = relationship(
        "WBSNode", remote_side=[id], backref="children"
    )
    activities: Mapped[List[Activity]] = relationship(
        "Activity", back_populates="wbs_node"
    )

    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_wbs_project_code"),
    )


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    wbs_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("wbs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    activity_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    activity_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, default="TT_Task"
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="NOT_STARTED", index=True
    )
    planned_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )
    planned_finish: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    actual_finish: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    original_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    remaining_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    percent_complete: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=0.0
    )
    calendar: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    project: Mapped[Project] = relationship("Project", back_populates="activities")
    wbs_node: Mapped[Optional[WBSNode]] = relationship(
        "WBSNode", back_populates="activities"
    )
    outgoing_relationships: Mapped[List[ActivityRelationship]] = relationship(
        "ActivityRelationship",
        foreign_keys="[ActivityRelationship.predecessor_id]",
        back_populates="predecessor",
        cascade="all, delete-orphan",
    )
    incoming_relationships: Mapped[List[ActivityRelationship]] = relationship(
        "ActivityRelationship",
        foreign_keys="[ActivityRelationship.successor_id]",
        back_populates="successor",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("project_id", "activity_code", name="uq_activity_project_code"),
        Index("ix_activities_proj_status", "project_id", "status"),
        Index("ix_activities_proj_wbs", "project_id", "wbs_id"),
    )


class ActivityRelationship(Base):
    __tablename__ = "activity_relationships"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    predecessor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    successor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(
        String(10), nullable=False, default="FS"
    )
    lag: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project: Mapped[Project] = relationship("Project", back_populates="relationships")
    predecessor: Mapped[Activity] = relationship(
        "Activity",
        foreign_keys=[predecessor_id],
        back_populates="outgoing_relationships",
    )
    successor: Mapped[Activity] = relationship(
        "Activity",
        foreign_keys=[successor_id],
        back_populates="incoming_relationships",
    )

    __table_args__ = (
        UniqueConstraint(
            "predecessor_id",
            "successor_id",
            "relationship_type",
            name="uq_relationship_pred_succ_type",
        ),
    )
