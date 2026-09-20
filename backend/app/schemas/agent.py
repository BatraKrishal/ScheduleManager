from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ConversationCreateRequest(BaseModel):
    active_activity_id: Optional[str] = None
    force_new: Optional[bool] = False
    title: Optional[str] = None


class MessageDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sender: str
    content: str
    message_metadata: Optional[Dict[str, Any]] = None
    created_at: str


class ConversationSummaryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    message_count: int = 0
    active_activity_id: Optional[str] = None
    active_event_id: Optional[str] = None


class ConversationDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: str
    project_id: str
    title: Optional[str] = "New Chat"
    status: str
    active_activity: Optional[Dict[str, Any]] = None
    active_event_id: Optional[str] = None
    clarification_turns: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    history: List[MessageDTO] = []


class MessageSendRequest(BaseModel):
    content: str


class ActionCardDTO(BaseModel):
    type: str  # "PROPOSAL_CONFIRMATION", "CLARIFICATION_CHOICE", "INFORMATIONAL"
    proposal_id: Optional[str] = None
    proposal_status: Optional[str] = None  # "PENDING", "CONSUMED", "APPLIED", "REJECTED", "EXPIRED"
    event_id: Optional[str] = None
    activity_id: Optional[str] = None
    activity_code: Optional[str] = None
    activity_name: Optional[str] = None
    current_percent: Optional[float] = None
    proposed_percent: Optional[float] = None
    incremental_quantity: Optional[float] = None
    unit: Optional[str] = None
    execution_date: Optional[str] = None
    question: Optional[str] = None
    options: Optional[List[Dict[str, Any]]] = None


class MessageResponseDTO(BaseModel):
    message_id: str
    sender: str
    reply_text: str
    action_card: Optional[ActionCardDTO] = None
    created_at: Optional[str] = None


class AttachmentResponseDTO(BaseModel):
    artifact_id: str
    filename: str
    extracted_events_count: int
    agent_message: str
    action_card: Optional[ActionCardDTO] = None


class ProposalConfirmRequest(BaseModel):
    proposal_id: str
    action: str = Field(default="CONFIRM")  # "CONFIRM", "REJECT"


class ProposalConfirmResponse(BaseModel):
    status: str  # "APPLIED", "REJECTED"
    activity_id: str
    activity_code: str
    previous_percent: float
    new_percent: float
    audit_log_id: str
    message: str


class ParsedConversationalIntent(BaseModel):
    intent: str  # "INFORMATION_QUERY", "PROGRESS_REPORT", "PROGRESS_UPDATE_REQUEST", "CLARIFICATION_RESPONSE", "ARTIFACT_SUBMISSION"
    confidence: float = 0.95
    entities_present: List[str] = []
    quantity: Optional[float] = None
    unit: Optional[str] = None
    quantity_semantics: str = "UNKNOWN"  # "INCREMENTAL", "CUMULATIVE", "UNKNOWN"
    location: Optional[str] = None
    discipline: Optional[str] = None
    contractor: Optional[str] = None
    asset: Optional[str] = None
    wbs_hint: Optional[str] = None
    reported_activity_code: Optional[str] = None
    execution_date: Optional[str] = None
    status_reported: str = "IN_PROGRESS"
    override_percent: Optional[float] = None
    description: Optional[str] = None
