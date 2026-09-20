from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.domain.database import get_db
from app.domain.models import Activity, Artifact, ExecutionEvent, Project, ScheduleAuditLog

router = APIRouter(tags=["Export & Audit"])


@router.get("/api/v1/projects/{project_id}/audit-trail")
def get_project_audit_trail(project_id: str, db: Session = Depends(get_db)):
    """
    Retrieve immutable audit log records for a project, showing full end-to-end
    provenance from schedule update -> ExecutionEvent -> Artifact -> MinIO storage key.
    """
    logs = (
        db.query(ScheduleAuditLog)
        .filter(ScheduleAuditLog.project_id == project_id)
        .order_by(ScheduleAuditLog.timestamp.desc())
        .all()
    )

    results = []
    for log in logs:
        artifact = db.query(Artifact).filter(Artifact.id == log.artifact_id).first() if log.artifact_id else None
        event = db.query(ExecutionEvent).filter(ExecutionEvent.id == log.execution_event_id).first() if log.execution_event_id else None
        activity = db.query(Activity).filter(Activity.id == log.activity_id).first() if log.activity_id else None

        results.append({
            "id": log.id,
            "project_id": log.project_id,
            "activity_id": log.activity_id,
            "activity_code": activity.activity_code if activity else None,
            "activity_name": activity.name if activity else None,
            "action": log.action,
            "user_id": log.user_id,
            "timestamp": log.timestamp.isoformat(),
            "previous_state": log.previous_state,
            "new_state": log.new_state,
            "execution_event": {
                "id": event.id if event else None,
                "verbatim_excerpt": event.verbatim_excerpt if event else None,
                "execution_date": event.execution_date.strftime("%Y-%m-%d") if event else None,
            } if event else None,
            "artifact": {
                "id": artifact.id if artifact else None,
                "original_filename": artifact.original_filename if artifact else None,
                "sha256": artifact.sha256 if artifact else None,
                "storage_key": artifact.storage_key if artifact else None,
                "storage_bucket": artifact.storage_bucket if artifact else None,
            } if artifact else None,
        })

    return {"project_id": project_id, "total_records": len(results), "audit_trail": results}


@router.get("/api/v1/projects/{project_id}/export/xer")
def export_p6_xer(project_id: str, db: Session = Depends(get_db)):
    """
    Export current authoritative project schedule into Primavera P6 .xer format,
    reflecting all verified field progress mutations.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found.",
        )

    activities = db.query(Activity).filter(Activity.project_id == project_id).all()

    # Generate P6 .xer format lines
    lines = [
        "ERMHDR\t8.3\t1984-01-01\tXER\tP6 Professional\r\n",
        "%T\tPROJECT\r\n",
        "%F\tproj_id\tproj_short_name\ttarget_start_date\ttarget_end_date\r\n",
        f"%R\t1\t{project.project_code}\t{project.planned_start.strftime('%Y-%m-%d') if project.planned_start else ''}\t{project.planned_finish.strftime('%Y-%m-%d') if project.planned_finish else ''}\r\n",
        "%T\tTASK\r\n",
        "%F\ttask_id\tproj_id\twbs_id\ttask_code\ttask_name\tstatus_code\tact_start_date\tact_end_date\tphys_complete_pct\r\n",
    ]

    for idx, act in enumerate(activities, start=1):
        status_code = "TK_Complete" if act.status == "COMPLETED" else ("TK_Active" if act.status == "IN_PROGRESS" else "TK_NotStart")
        act_start = act.actual_start.strftime("%Y-%m-%d %H:%M") if act.actual_start else ""
        act_finish = act.actual_finish.strftime("%Y-%m-%d %H:%M") if act.actual_finish else ""
        pct = act.percent_complete or 0.0

        lines.append(
            f"%R\t{idx}\t1\t1\t{act.activity_code}\t{act.name}\t{status_code}\t{act_start}\t{act_finish}\t{pct:.2f}\r\n"
        )

    lines.append("%E\r\n")
    xer_content = "".join(lines)

    return Response(
        content=xer_content.encode("utf-8"),
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{project.project_code}_updated.xer"'
        },
    )
