from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.domain.database import get_db
from app.schemas.agent import (
    AttachmentResponseDTO,
    BulkProposalConfirmRequest,
    BulkProposalConfirmResponse,
    ConversationCreateRequest,
    ConversationDTO,
    ConversationSummaryDTO,
    MessageResponseDTO,
    MessageSendRequest,
    ProposalConfirmRequest,
    ProposalConfirmResponse,
)
from app.services.agent_service import TimeAgentService

logger = logging.getLogger("agent_api")

router = APIRouter(tags=["Time Agent"])


@router.get(
    "/api/v1/projects/{project_id}/agent/conversations",
    response_model=List[ConversationSummaryDTO],
    status_code=status.HTTP_200_OK,
)
def list_conversations(
    project_id: str,
    q: Optional[str] = Query(default=None, description="Search query matching title and message content"),
    x_user_id: str = Header(default="site-supervisor", alias="X-User-ID"),
    db: Session = Depends(get_db),
):
    """
    List lightweight conversation summaries strictly scoped to the specified project.
    Supports search query parameter `q` matching title and message content.
    Ordered by most recently updated first.
    """
    return TimeAgentService.list_conversations(
        db=db,
        project_id=project_id,
        user_id=x_user_id,
        search_query=q,
    )


@router.post(
    "/api/v1/projects/{project_id}/agent/conversations",
    response_model=ConversationDTO,
    status_code=status.HTTP_200_OK,
)
def start_or_get_conversation(
    project_id: str,
    payload: Optional[ConversationCreateRequest] = None,
    x_user_id: str = Header(default="site-supervisor", alias="X-User-ID"),
    db: Session = Depends(get_db),
):
    """
    Start a new conversational execution reporting session or retrieve an active one.
    Accepts optional active_activity_id from UI anchoring, and force_new boolean for + New Chat.
    """
    active_act_id = payload.active_activity_id if payload else None
    force_new = payload.force_new if payload else False
    title = payload.title if payload else None
    return TimeAgentService.get_or_create_conversation(
        db=db,
        project_id=project_id,
        user_id=x_user_id,
        active_activity_id=active_act_id,
        force_new=force_new,
        title=title,
    )


@router.get(
    "/api/v1/projects/{project_id}/agent/conversations/{conversation_id}",
    response_model=ConversationDTO,
)
def get_conversation(
    project_id: str,
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """
    Fetch current conversation details and message history.
    Enforces strict project scoping: rejects if conversation does not belong to project_id.
    """
    from app.domain.models import Conversation
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.project_id == project_id)
        .first()
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found in project {project_id}.",
        )
    return TimeAgentService._to_conversation_dto(db, conv)


@router.post(
    "/api/v1/projects/{project_id}/agent/conversations/{conversation_id}/messages",
    response_model=MessageResponseDTO,
    status_code=status.HTTP_200_OK,
)
def send_agent_message(
    project_id: str,
    conversation_id: str,
    payload: MessageSendRequest,
    x_user_id: str = Header(default="site-supervisor", alias="X-User-ID"),
    db: Session = Depends(get_db),
):
    """
    Send a natural language progress report, update request, or clarification answer.
    """
    return TimeAgentService.process_message(
        db=db,
        project_id=project_id,
        conversation_id=conversation_id,
        user_content=payload.content,
        caller_id=x_user_id,
    )


@router.post(
    "/api/v1/projects/{project_id}/agent/conversations/{conversation_id}/attachments",
    response_model=AttachmentResponseDTO,
    status_code=status.HTTP_201_CREATED,
)
def upload_agent_attachment(
    project_id: str,
    conversation_id: str,
    file: UploadFile = File(...),
    x_user_id: str = Header(default="site-supervisor", alias="X-User-ID"),
    db: Session = Depends(get_db),
):
    """
    Upload a field report file (PDF, XLSX, CSV, or Audio) into the active conversation.
    Artifact is stored in MinIO and extracted into ExecutionEvents bound to the conversation.
    """
    content = file.file.read()
    return TimeAgentService.process_attachment(
        db=db,
        project_id=project_id,
        conversation_id=conversation_id,
        file_bytes=content,
        filename=file.filename,
        caller_id=x_user_id,
    )


@router.post(
    "/api/v1/projects/{project_id}/agent/conversations/{conversation_id}/confirm",
    response_model=ProposalConfirmResponse,
    status_code=status.HTTP_200_OK,
)
def confirm_update_proposal(
    project_id: str,
    conversation_id: str,
    payload: ProposalConfirmRequest,
    x_user_id: str = Header(default="site-supervisor", alias="X-User-ID"),
    db: Session = Depends(get_db),
):
    """
    Explicitly confirm a staged update proposal.
    Executes an atomic row-locked transaction against PostgreSQL and mutates schedule progress.
    """
    if payload.action.upper() == "REJECT":
        from app.domain.models import UpdateProposal
        prop = (
            db.query(UpdateProposal)
            .filter(
                UpdateProposal.id == payload.proposal_id,
                UpdateProposal.conversation_id == conversation_id,
                UpdateProposal.project_id == project_id,
            )
            .first()
        )
        if not prop:
            raise HTTPException(status_code=404, detail="Proposal not found.")
        prop.status = "REJECTED"
        db.commit()
        return ProposalConfirmResponse(
            status="REJECTED",
            activity_id=prop.matched_activity_id,
            activity_code="N/A",
            previous_percent=0.0,
            new_percent=0.0,
            audit_log_id="none",
            message="Proposal was rejected.",
        )

    return TimeAgentService.confirm_proposal(
        db=db,
        project_id=project_id,
        conversation_id=conversation_id,
        proposal_id=payload.proposal_id,
        caller_id=x_user_id,
    )


@router.post(
    "/api/v1/projects/{project_id}/agent/conversations/{conversation_id}/bulk-confirm",
    response_model=BulkProposalConfirmResponse,
    status_code=status.HTTP_200_OK,
)
def confirm_bulk_update_proposal(
    project_id: str,
    conversation_id: str,
    payload: BulkProposalConfirmRequest,
    x_user_id: str = Header(default="site-supervisor", alias="X-User-ID"),
    db: Session = Depends(get_db),
):
    """
    Explicitly confirm a staged bulk update proposal.
    Executes an atomic schedule mutation across all confirmed activities.
    """
    return TimeAgentService.confirm_bulk_proposal(
        db=db,
        project_id=project_id,
        conversation_id=conversation_id,
        payload=payload,
        caller_id=x_user_id,
    )
