from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.domain.models import (
    Activity,
    Artifact,
    Conversation,
    ConversationMessage,
    ExecutionEvent,
    Project,
    ScheduleAuditLog,
    UpdateProposal,
    WBSNode,
)
from app.schemas.agent import (
    ActionCardDTO,
    AttachmentResponseDTO,
    BulkProposalConfirmRequest,
    BulkProposalConfirmResponse,
    ConversationCreateRequest,
    ConversationDTO,
    ConversationSummaryDTO,
    MessageDTO,
    MessageResponseDTO,
    ParsedConversationalIntent,
    ProposalConfirmResponse,
)
from app.services.agent_parser import ConversationalParser
from app.services.extraction_service import ExtractionService
from app.services.matching_service import MatchingService
from app.services.minio_service import minio_service
from app.services.schedule_update_service import ScheduleUpdateService
from app.services.validation_service import ValidationException

logger = logging.getLogger("agent_service")


class TimeAgentService:
    @classmethod
    def _generate_conversation_title(
        cls,
        text: str,
        parsed: Optional[ParsedConversationalIntent] = None,
    ) -> str:
        """
        Deterministic 3-7 word conversation title generation based on user message and parsed signals.
        Never makes external API calls.
        """
        lower = text.lower()
        loc = parsed.location if parsed and parsed.location else None
        act_code = parsed.reported_activity_code if parsed and parsed.reported_activity_code else None

        # Look for construction tags like F-204, CT-07, CIV-1001
        code_match = re.search(r"\b([A-Z]{1,4}-\d{2,5})\b", text, re.IGNORECASE)
        anchor = loc or (code_match.group(1).upper() if code_match else act_code)

        if anchor and "concrete" in lower:
            return f"{anchor} Concrete Pour"
        if anchor and ("cable" in lower or "tray" in lower):
            return f"{anchor} Cable Tray Progress"
        if anchor and ("pipe" in lower or "piping" in lower):
            return f"{anchor} Piping Progress"
        if anchor and "foundation" in lower:
            return f"{anchor} Foundation Progress"
        if anchor and ("update" in lower or "%" in lower):
            return f"{anchor} Progress Update"
        if anchor:
            return f"{anchor} Execution Report"

        if "upcoming" in lower and "civil" in lower:
            return "Upcoming Civil Activities"
        if "upcoming" in lower and "activit" in lower:
            return "Upcoming Activities"
        if "concrete" in lower and ("pour" in lower or "poured" in lower):
            return "Concrete Pour Progress"
        if "cable tray" in lower:
            return "Cable Tray Progress"
        if "piping" in lower:
            return "Piping Progress"
        if "pump" in lower and ("install" in lower or "installation" in lower):
            return "Pump Installation"
        if "pump" in lower:
            return "Pump Installation"
        if "inspection" in lower:
            return "Foundation Inspection"
        if "mechanical" in lower:
            return "Mechanical Progress"
        if "electrical" in lower:
            return "Electrical Progress"

        # Fallback: clean words
        words = [
            w.strip(",.!?\"';:()[]{}")
            for w in text.split()
            if w.lower() not in {
                "we", "i", "can", "you", "please", "the", "a", "an", "is", "are",
                "for", "to", "in", "at", "today", "yesterday", "our", "all",
            }
        ]
        clean_words = [w for w in words if w]
        if clean_words:
            cand = " ".join(clean_words[:5]).title()
            return cand[:45].strip()

        return "Site Progress Report"

    @classmethod
    def get_or_create_conversation(
        cls,
        db: Session,
        project_id: str,
        user_id: str = "site-supervisor",
        active_activity_id: Optional[str] = None,
        force_new: bool = False,
        title: Optional[str] = None,
    ) -> ConversationDTO:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found.",
            )

        conv = None
        if not force_new:
            # Look for existing active conversation for this user and project
            conv = (
                db.query(Conversation)
                .filter(
                    Conversation.project_id == project_id,
                    Conversation.user_id == user_id,
                    Conversation.status.in_(["ACTIVE", "WAITING_FOR_USER"]),
                )
                .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
                .first()
            )

        if not conv:
            conv = Conversation(
                id=f"conv-{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                title=title or "New Chat",
                user_id=user_id,
                active_activity_id=active_activity_id,
                status="ACTIVE",
            )
            db.add(conv)
            db.commit()
            db.refresh(conv)
        elif active_activity_id and conv.active_activity_id != active_activity_id:
            conv.active_activity_id = active_activity_id
            conv.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(conv)

        return cls._to_conversation_dto(db, conv)

    @classmethod
    def list_conversations(
        cls,
        db: Session,
        project_id: str,
        user_id: str = "site-supervisor",
        search_query: Optional[str] = None,
    ) -> List[ConversationSummaryDTO]:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found.",
            )

        # Base query strictly scoped to project_id - HARD ISOLATION
        base_query = db.query(Conversation).filter(
            Conversation.project_id == project_id,
        )

        if search_query and search_query.strip():
            term = f"%{search_query.strip()}%"
            matching_msg_conv_ids = (
                db.query(ConversationMessage.conversation_id)
                .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
                .filter(
                    Conversation.project_id == project_id,
                    ConversationMessage.content.ilike(term),
                )
            )
            base_query = base_query.filter(
                or_(
                    Conversation.title.ilike(term),
                    Conversation.id.in_(matching_msg_conv_ids),
                )
            )

        conversations = (
            base_query
            .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
            .all()
        )

        conv_ids = [c.id for c in conversations]
        msg_counts = {}
        if conv_ids:
            counts = (
                db.query(ConversationMessage.conversation_id, func.count(ConversationMessage.id))
                .filter(ConversationMessage.conversation_id.in_(conv_ids))
                .group_by(ConversationMessage.conversation_id)
                .all()
            )
            msg_counts = {cid: cnt for cid, cnt in counts}

        summaries = []
        for c in conversations:
            summaries.append(
                ConversationSummaryDTO(
                    id=c.id,
                    project_id=c.project_id,
                    title=c.title or "New Chat",
                    status=c.status,
                    created_at=c.created_at.isoformat() if c.created_at else datetime.utcnow().isoformat(),
                    updated_at=c.updated_at.isoformat() if c.updated_at else datetime.utcnow().isoformat(),
                    message_count=msg_counts.get(c.id, 0),
                    active_activity_id=c.active_activity_id,
                    active_event_id=c.active_event_id,
                )
            )
        return summaries

    @classmethod
    def _to_conversation_dto(cls, db: Session, conv: Conversation) -> ConversationDTO:
        act_dict = None
        if conv.active_activity_id:
            act = db.query(Activity).filter(Activity.id == conv.active_activity_id).first()
            if act:
                act_dict = {
                    "activity_id": act.id,
                    "activity_code": act.activity_code,
                    "name": act.name,
                    "percent_complete": act.percent_complete or 0.0,
                    "status": act.status,
                }

        messages = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conv.id)
            .order_by(ConversationMessage.created_at.asc())
            .all()
        )
        msg_dtos = []
        for m in messages:
            meta = json.loads(m.message_metadata) if m.message_metadata else None
            # Enrich proposal status from authoritative update_proposals table
            if meta and meta.get("type") == "PROPOSAL_CONFIRMATION" and meta.get("proposal_id"):
                prop = (
                    db.query(UpdateProposal)
                    .filter(UpdateProposal.id == meta["proposal_id"])
                    .first()
                )
                if prop:
                    if prop.status == "PENDING" and datetime.utcnow() > prop.expires_at:
                        meta["proposal_status"] = "EXPIRED"
                    else:
                        meta["proposal_status"] = prop.status

            msg_dtos.append(
                MessageDTO(
                    id=m.id,
                    sender=m.sender,
                    content=m.content,
                    message_metadata=meta,
                    created_at=m.created_at.isoformat(),
                )
            )

        return ConversationDTO(
            conversation_id=conv.id,
            project_id=conv.project_id,
            title=conv.title or "New Chat",
            status=conv.status,
            active_activity=act_dict,
            active_event_id=conv.active_event_id,
            clarification_turns=conv.clarification_turns,
            created_at=conv.created_at.isoformat() if conv.created_at else None,
            updated_at=conv.updated_at.isoformat() if conv.updated_at else None,
            history=msg_dtos,
        )

    @classmethod
    def process_message(
        cls,
        db: Session,
        project_id: str,
        conversation_id: str,
        user_content: str,
        caller_id: str = "site-supervisor",
    ) -> MessageResponseDTO:
        # 1. Validate conversation and project
        conv = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.project_id == project_id)
            .first()
        )
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found for project {project_id}.",
            )

        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        # Record user message
        user_msg = ConversationMessage(
            id=f"msg-{uuid.uuid4().hex[:8]}",
            conversation_id=conv.id,
            sender="USER",
            content=user_content,
        )
        db.add(user_msg)
        db.flush()

        active_act_code = None
        if conv.active_activity_id:
            act = db.query(Activity).filter(Activity.id == conv.active_activity_id).first()
            if act:
                active_act_code = act.activity_code

        is_clarification = (conv.active_event_id is not None and conv.clarification_turns > 0)

        # 2. Conversational Intent & Entity Extraction via Gemini (with rule fallback)
        parsed = ConversationalParser.parse_message(
            text=user_content,
            project_data_date=project.data_date,
            active_activity_code=active_act_code,
            is_clarification_turn=is_clarification,
        )

        # 2b. Automatically generate deterministic title on first meaningful message
        if not conv.title or conv.title == "New Chat":
            conv.title = cls._generate_conversation_title(user_content, parsed)
        conv.updated_at = datetime.utcnow()
        db.flush()

        # 2c. Check for explicit user cancellation requests (e.g. "cancel", "cancel this update", "cancel proposal")
        clean_user_txt = user_content.strip().lower().rstrip(".,;:!?")
        if any(clean_user_txt == c or clean_user_txt.startswith(c) for c in [
            "cancel", "cancel this", "cancel update", "cancel this update", "cancel it", "cancel proposal", "don't update", "abort"
        ]):
            if conv.active_event_id:
                active_ev = db.query(ExecutionEvent).filter(ExecutionEvent.id == conv.active_event_id).first()
                if active_ev:
                    active_ev.status = "REJECTED"
                pending_props = db.query(UpdateProposal).filter(
                    UpdateProposal.conversation_id == conv.id,
                    UpdateProposal.status == "PENDING",
                ).all()
                for p in pending_props:
                    p.status = "REJECTED"
                conv.active_event_id = None
                conv.status = "ACTIVE"
                db.commit()
                reply_text = "Update cancelled. No changes were applied to the schedule."
                return cls._save_and_return_agent_response(db, conv, reply_text, action_card=None)
            else:
                prior_agent_msgs = (
                    db.query(ConversationMessage)
                    .filter(ConversationMessage.conversation_id == conv.id, ConversationMessage.sender == "AGENT")
                    .order_by(ConversationMessage.created_at.desc())
                    .limit(5)
                    .all()
                )
                was_recently_updated = any(
                    any(term in m.content.lower() for term in ["successfully updated", "successfully applied", "confirmed and applied"])
                    for m in prior_agent_msgs
                )
                if was_recently_updated:
                    reply_text = (
                        "The previous update has already been committed and applied to the authoritative schedule ledger. "
                        "Committed progress cannot be simply undone with a cancel command; to adjust or revert progress, "
                        "please report the new progress percentage (e.g., 'set ELE-1001 to 0%') or update the activities in the Activities Table."
                    )
                else:
                    reply_text = "There are no pending updates or proposals to cancel."
                return cls._save_and_return_agent_response(db, conv, reply_text, action_card=None)

        # 3. Branch by Intent
        if parsed.intent == "INFORMATION_QUERY":
            reply_text = cls._handle_information_query(db, project, conv, parsed, user_content)
            agent_msg = ConversationMessage(
                id=f"msg-{uuid.uuid4().hex[:8]}",
                conversation_id=conv.id,
                sender="AGENT",
                content=reply_text,
            )
            db.add(agent_msg)
            db.commit()
            return MessageResponseDTO(
                message_id=agent_msg.id,
                sender="AGENT",
                reply_text=reply_text,
                action_card=None,
                created_at=agent_msg.created_at.isoformat(),
            )

        if parsed.intent == "BULK_PROGRESS_REPORT" or (parsed.is_bulk and not is_clarification):
            return cls._handle_bulk_progress(
                db=db,
                project=project,
                conv=conv,
                parsed=parsed,
                raw_text=user_content,
                trigger_message_id=user_msg.id,
                caller_id=caller_id,
            )

        # Handle Progress Report / Update Request / Clarification
        return cls._handle_progress_or_clarification(
            db=db,
            project=project,
            conv=conv,
            parsed=parsed,
            raw_text=user_content,
            trigger_message_id=user_msg.id,
            caller_id=caller_id,
        )

    @classmethod
    def _handle_information_query(
        cls,
        db: Session,
        project: Project,
        conv: Conversation,
        parsed: ParsedConversationalIntent,
        raw_text: str,
    ) -> str:
        # If active activity is anchored, return its status
        if conv.active_activity_id:
            act = db.query(Activity).filter(Activity.id == conv.active_activity_id).first()
            if act:
                wbs = db.query(WBSNode).filter(WBSNode.id == act.wbs_id).first() if act.wbs_id else None
                return (
                    f"Activity {act.activity_code} ({act.name}) is currently {act.status} "
                    f"at {act.percent_complete or 0.0}% complete. "
                    f"Planned start: {act.planned_start.strftime('%Y-%m-%d') if act.planned_start else 'N/A'}, "
                    f"Planned finish: {act.planned_finish.strftime('%Y-%m-%d') if act.planned_finish else 'N/A'}. "
                    f"WBS: {wbs.name if wbs else 'N/A'}."
                )

        # Query activity by code if cited
        if parsed.reported_activity_code:
            act = (
                db.query(Activity)
                .filter(
                    Activity.project_id == project.id,
                    Activity.activity_code == parsed.reported_activity_code,
                )
                .first()
            )
            if act:
                return (
                    f"Activity {act.activity_code} ({act.name}) is {act.status} "
                    f"with {act.percent_complete or 0.0}% progress recorded."
                )

        # Check for historical knowledge / productivity / duration questions
        lower = raw_text.lower()
        is_historical = any(
            term in lower
            for term in [
                "historical", "observed", "production rate", "rate of", "how long did",
                "past", "average duration", "planned vs actual", "variance", "productivity",
                "per day", "per reporting day", "history", "benchmark", "how much did we install",
                "pouring rate", "installation rate"
            ]
        )
        if is_historical:
            q_type = "PRODUCTIVITY"
            if any(term in lower for term in ["duration", "long", "time taken", "variance"]):
                q_type = "DURATION"
            elif any(term in lower for term in ["history", "records", "ledger"]):
                q_type = "EXECUTION_HISTORY"

            disc = parsed.discipline
            if not disc:
                if "pipe" in lower or "piping" in lower:
                    disc = "Piping"
                elif "concrete" in lower or "civil" in lower or "foundation" in lower:
                    disc = "Civil"
                elif "cable" in lower or "electrical" in lower:
                    disc = "Electrical"
                elif "mechanical" in lower:
                    disc = "Mechanical"

            act_code = parsed.reported_activity_code

            tool_res = cls.query_historical_performance(
                db=db,
                project_id=project.id,
                query_type=q_type,
                discipline=disc,
                activity_code=act_code,
                unit=parsed.unit,
            )
            summary = tool_res.get("summary", "")
            evidence_count = len(tool_res.get("evidence", []))
            if evidence_count > 0:
                summary += f"\n\n[Verified Evidence: {evidence_count} authoritative ledger record(s) in PostgreSQL]"
            return summary

        # General project summary
        act_count = db.query(Activity).filter(Activity.project_id == project.id).count()
        data_date_str = project.data_date.strftime('%Y-%m-%d') if project.data_date else 'Current'
        return (
            f"Project {project.name} ({project.project_code}) has {act_count} activities. "
            f"Current data date is {data_date_str}. You can report progress by stating quantities and locations "
            f"(e.g., 'We poured 35 m3 for F-204 today')."
        )

    @classmethod
    def query_historical_performance(
        cls,
        db: Session,
        project_id: str,
        query_type: str = "PRODUCTIVITY",
        discipline: Optional[str] = None,
        activity_code: Optional[str] = None,
        unit: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Read-only Time Agent tool to query historical performance and productivity records.
        Strictly scopes to project_id.
        PostgreSQL is authoritative: returns deterministic calculation with evidence records.
        """
        from app.schemas.institutional_memory import HistoricalQueryRequest
        from app.services.institutional_memory_service import InstitutionalMemoryService

        req = HistoricalQueryRequest(
            query_type=query_type,
            discipline=discipline,
            activity_code=activity_code,
            unit=unit,
        )
        res = InstitutionalMemoryService.execute_query(db, project_id, req)
        return res.model_dump()

    @classmethod
    def _handle_bulk_progress(
        cls,
        db: Session,
        project: Project,
        conv: Conversation,
        parsed: ParsedConversationalIntent,
        raw_text: str,
        trigger_message_id: str,
        caller_id: str,
        active_event: Optional[ExecutionEvent] = None,
    ) -> MessageResponseDTO:
        """
        Governed bulk intent handler.
        The LLM NEVER determines activity membership.
        The backend queries the authoritative database for activities matching the extracted scope.
        """
        scope = parsed.bulk_scope or {}
        disc = scope.get("discipline") or parsed.discipline
        loc = scope.get("location") or parsed.location
        kw = scope.get("keyword")

        # Query authoritative active activities for this project
        query = db.query(Activity).filter(
            Activity.project_id == project.id,
            Activity.status != "COMPLETED",
        )

        all_acts = query.all()
        matched_acts: List[Activity] = []

        for act in all_acts:
            match = False
            # 1. Match discipline
            if disc:
                if act.discipline and disc.lower() in act.discipline.lower():
                    match = True
                elif disc.lower() in act.name.lower():
                    match = True
            # 2. Match keyword
            if kw and (kw.lower() in act.name.lower() or (act.discipline and kw.lower() in act.discipline.lower())):
                match = True
            # 3. Match location if specified
            if loc and act.location_code and loc.lower() in act.location_code.lower():
                match = True

            if match and act not in matched_acts:
                matched_acts.append(act)

        # Fallback 1: if specific discipline/keyword didn't find any, but user mentioned words in raw_text
        if not matched_acts:
            clean_tokens = [
                w for w in re.findall(r"[A-Za-z0-9]+", raw_text.lower())
                if len(w) > 3 and w not in ["have", "completed", "finish", "finished", "update", "them", "these", "project", "work", "activities", "activity", "both"]
            ]
            if clean_tokens:
                for act in all_acts:
                    if any(tok in act.name.lower() or (act.discipline and tok in act.discipline.lower()) for tok in clean_tokens):
                        if act not in matched_acts:
                            matched_acts.append(act)

        # Fallback 2: If during clarification or active event, resolve to candidate activities of the active event
        if not matched_acts:
            active_ev = active_event
            if not active_ev and conv.active_event_id:
                active_ev = db.query(ExecutionEvent).filter(ExecutionEvent.id == conv.active_event_id).first()
            if active_ev:
                eval_res = MatchingService.evaluate_event_for_agent(db, active_ev)
                cands = eval_res.all_candidates
                if cands:
                    cand_slice = [c for c in cands if c.match_score >= 0.25]
                    if len(cand_slice) < 2 and len(cands) >= 2:
                        cand_slice = cands[:2]
                    elif not cand_slice:
                        cand_slice = cands[:4]
                    cand_ids = [c.activity_id for c in cand_slice]
                    acts_found = db.query(Activity).filter(Activity.id.in_(cand_ids)).all()
                    act_map = {a.id: a for a in acts_found}
                    for cid in cand_ids:
                        if cid in act_map and act_map[cid] not in matched_acts:
                            matched_acts.append(act_map[cid])

        target_pct = parsed.override_percent if parsed.override_percent is not None else 100.0
        scope_desc = f"{disc} " if disc else (f"{kw} " if kw else "")
        scope_desc = f"{scope_desc}activities".strip()
        if scope_desc == "activities":
            scope_desc = "matching candidate activities"

        if len(matched_acts) == 0:
            reply_text = (
                f"I could not find any active activities matching '{raw_text}' in project {project.name}. "
                f"Could you please specify which activity code or work package this progress belongs to?"
            )
            return cls._save_and_return_agent_response(db=db, conv=conv, reply_text=reply_text, action_card=None)

        if len(matched_acts) == 1:
            # Single activity match -> route to single proposal
            target_act = matched_acts[0]
            prev_pct = target_act.percent_complete or 0.0
            event = ExecutionEvent(
                id=f"ev-{uuid.uuid4().hex[:8]}",
                project_id=project.id,
                source_type="CONVERSATION",
                conversation_id=conv.id,
                message_id=trigger_message_id,
                verbatim_excerpt=raw_text,
                description=parsed.description or raw_text,
                reported_activity_code=target_act.activity_code,
                execution_date=project.data_date or datetime.utcnow(),
                status_reported=parsed.status_reported or "COMPLETED",
                extraction_confidence=1.0,
                status="DRAFT",
            )
            db.add(event)
            db.flush()
            conv.active_event_id = event.id
            proposal = cls.stage_proposal(
                db=db,
                conversation=conv,
                event=event,
                activity=target_act,
                proposed_percent=target_pct,
                proposed_status="COMPLETED" if target_pct == 100.0 else "IN_PROGRESS",
                quantity_semantics="INCREMENTAL",
                override_percent=target_pct,
            )
            card = ActionCardDTO(
                type="PROPOSAL_CONFIRMATION",
                proposal_id=proposal.id,
                event_id=event.id,
                activity_id=target_act.id,
                activity_code=target_act.activity_code,
                activity_name=target_act.name,
                current_percent=prev_pct,
                proposed_percent=target_pct,
                execution_date=event.execution_date.strftime("%Y-%m-%d"),
            )
            reply_text = (
                f"I've matched this to {target_act.activity_code} ({target_act.name}). "
                f"This will advance progress from {prev_pct}% to {target_pct}%. "
                f"Please confirm to apply this update to the authoritative schedule."
            )
            return cls._save_and_return_agent_response(db=db, conv=conv, reply_text=reply_text, action_card=card)

        if 2 <= len(matched_acts) <= 6:
            bulk_act_dtos = [
                {
                    "activity_id": act.id,
                    "activity_code": act.activity_code,
                    "activity_name": act.name,
                    "current_percent": act.percent_complete or 0.0,
                    "proposed_percent": target_pct,
                }
                for act in matched_acts
            ]

            card = ActionCardDTO(
                type="BULK_SCOPE_PROPOSAL",
                bulk_activities=bulk_act_dtos,
                bulk_count=len(matched_acts),
                scope_label=scope_desc.title(),
                proposed_status="COMPLETED" if target_pct == 100.0 else "IN_PROGRESS",
                target_percent=target_pct,
                options=[
                    {
                        "label": f"Update All {len(matched_acts)} to {target_pct}%",
                        "value": "CONFIRM_ALL_BULK",
                    },
                    *[
                        {
                            "label": f"{a.activity_code} - {a.name}",
                            "value": a.activity_code,
                        }
                        for a in matched_acts
                    ],
                    {
                        "label": "Cancel",
                        "value": "CANCEL",
                    },
                ],
            )
            reply_text = (
                f"I found {len(matched_acts)} {scope_desc} in this project. "
                f"Do you want to update all {len(matched_acts)} to {target_pct}%, or select a specific activity?"
            )
            return cls._save_and_return_agent_response(
                db=db,
                conv=conv,
                reply_text=reply_text,
                action_card=card,
            )

        # More than 6 activities -> summarize + scoped review
        bulk_act_dtos = [
            {
                "activity_id": act.id,
                "activity_code": act.activity_code,
                "activity_name": act.name,
                "current_percent": act.percent_complete or 0.0,
                "proposed_percent": target_pct,
            }
            for act in matched_acts[:5]
        ]
        card = ActionCardDTO(
            type="BULK_SCOPE_PROPOSAL",
            bulk_activities=bulk_act_dtos,
            bulk_count=len(matched_acts),
            scope_label=scope_desc.title(),
            proposed_status="COMPLETED" if target_pct == 100.0 else "IN_PROGRESS",
            target_percent=target_pct,
            options=[
                {
                    "label": f"Review all {len(matched_acts)} activities in schedule table",
                    "value": "REVIEW_IN_TABLE",
                },
                {
                    "label": "Cancel",
                    "value": "CANCEL",
                },
            ],
        )
        reply_text = (
            f"I found {len(matched_acts)} {scope_desc} in this project schedule. "
            f"Because this is a broad work package, updating all of them at once requires review in the Activities Table, "
            f"or you can specify a specific area or block to narrow down the scope."
        )
        return cls._save_and_return_agent_response(
            db=db,
            conv=conv,
            reply_text=reply_text,
            action_card=card,
        )

    @classmethod
    def _handle_progress_or_clarification(
        cls,
        db: Session,
        project: Project,
        conv: Conversation,
        parsed: ParsedConversationalIntent,
        raw_text: str,
        trigger_message_id: str,
        caller_id: str,
    ) -> MessageResponseDTO:
        event = None

        # Check if we are enriching an in-flight draft event
        if conv.active_event_id:
            event = (
                db.query(ExecutionEvent)
                .filter(
                    ExecutionEvent.id == conv.active_event_id,
                    ExecutionEvent.project_id == project.id,
                )
                .first()
            )

        if event and conv.clarification_turns > 0:
            # ENRICH EXISTING DRAFT EVENT
            logger.info(f"Enriching existing draft ExecutionEvent {event.id} on turn {conv.clarification_turns}")
            if parsed.location:
                event.location = parsed.location
            if parsed.quantity is not None:
                event.quantity = parsed.quantity
            if parsed.unit:
                event.unit = parsed.unit
            if parsed.discipline:
                event.discipline = parsed.discipline
            if parsed.reported_activity_code:
                event.reported_activity_code = parsed.reported_activity_code
            elif not event.reported_activity_code:
                # If supervisor answered a clarification question with an activity or foundation/location hint
                clean_ans = raw_text.strip().rstrip(".,;:!?").lower()

                # 1. Handle "None of these"
                if clean_ans in ["none_of_these", "none of these", "neither", "none", "no"]:
                    if conv.clarification_turns >= 2:
                        event.status = "IN_REVIEW"
                        conv.active_event_id = None
                        conv.status = "ACTIVE"
                        reply_text = "I could not resolve this report after clarification. I have routed it to the Lead Planner Review Queue for manual verification."
                        return cls._save_and_return_agent_response(db=db, conv=conv, reply_text=reply_text, action_card=None)
                    else:
                        conv.clarification_turns += 1
                        conv.status = "WAITING_FOR_USER"
                        reply_text = "Understood. Could you please specify the exact activity code (e.g., ELE-1001) or work package name?"
                        return cls._save_and_return_agent_response(db=db, conv=conv, reply_text=reply_text, action_card=None)

                # 2. Handle "All of them" / bulk intent during clarification turn
                if parsed.is_bulk or any(clean_ans == term or clean_ans.startswith(term) for term in [
                    "all of them", "all", "both", "both of them", "all of these", "update all", "update all of them", "all activities"
                ]):
                    if not parsed.discipline and event.discipline:
                        parsed.discipline = event.discipline
                    if not parsed.bulk_scope:
                        parsed.bulk_scope = {}
                    if not parsed.bulk_scope.get("discipline") and event.discipline:
                        parsed.bulk_scope["discipline"] = event.discipline
                    if not parsed.bulk_scope.get("keyword") and event.description:
                        parsed.bulk_scope["keyword"] = event.description

                    return cls._handle_bulk_progress(
                        db=db,
                        project=project,
                        conv=conv,
                        parsed=parsed,
                        raw_text=event.verbatim_excerpt or raw_text,
                        trigger_message_id=event.message_id or f"msg-{uuid.uuid4().hex[:8]}",
                        caller_id=caller_id,
                        active_event=event,
                    )

                matching_acts = db.query(Activity).filter(Activity.project_id == project.id).all()
                clean_tokens = [t for t in re.findall(r"[A-Za-z0-9]+-[A-Za-z0-9]+|[A-Za-z0-9]+", clean_ans) if len(t) > 2]
                for act in matching_acts:
                    if clean_ans == act.activity_code.lower() or (act.location_code and clean_ans == act.location_code.lower()):
                        event.reported_activity_code = act.activity_code
                        break
                    if any(ct in act.name.lower() or (act.location_code and ct in act.location_code.lower()) for ct in clean_tokens):
                        event.reported_activity_code = act.activity_code
                        break
            if raw_text:
                event.description = f"{event.description} {raw_text}".strip()
                event.verbatim_excerpt = f"{event.verbatim_excerpt} {raw_text}".strip()

            resolved_date = ConversationalParser.resolve_date(parsed.execution_date, project.data_date)
            if resolved_date:
                event.execution_date = resolved_date
                if event.extraction_notes:
                    event.extraction_notes = event.extraction_notes.replace("[DATE_NEEDED]", "").strip()

            # Append transcript to extraction_notes
            notes = event.extraction_notes or ""
            event.extraction_notes = f"{notes}\n[Clarification Turn {conv.clarification_turns}]: {raw_text}".strip()
            db.flush()
        else:
            # CREATE NEW DRAFT EXECUTION EVENT
            resolved_date = ConversationalParser.resolve_date(parsed.execution_date, project.data_date)
            date_needed = resolved_date is None
            event_date = resolved_date or project.data_date or datetime.utcnow()

            reported_code = parsed.reported_activity_code
            if not reported_code and conv.active_activity_id and "this" in raw_text.lower():
                act = db.query(Activity).filter(Activity.id == conv.active_activity_id).first()
                if act:
                    reported_code = act.activity_code

            initial_notes = "[DATE_NEEDED]" if date_needed else ""

            event = ExecutionEvent(
                id=f"ev-{uuid.uuid4().hex[:8]}",
                project_id=project.id,
                artifact_id=None,
                source_type="CONVERSATION",
                conversation_id=conv.id,
                message_id=trigger_message_id,
                verbatim_excerpt=raw_text,
                description=parsed.description or raw_text,
                reported_activity_code=reported_code,
                execution_date=event_date,
                status_reported=parsed.status_reported,
                quantity=parsed.quantity,
                unit=parsed.unit,
                location=parsed.location,
                discipline=parsed.discipline,
                contractor=parsed.contractor,
                asset=parsed.asset,
                wbs_hint=parsed.wbs_hint,
                extraction_confidence=parsed.confidence,
                extraction_notes=initial_notes,
                status="DRAFT",
            )
            db.add(event)
            db.flush()
            conv.active_event_id = event.id
            conv.clarification_turns = 0
            db.flush()

        # Deterministic non-finalizing evaluation
        eval_result = MatchingService.evaluate_event_for_agent(db, event)

        # Branch on Matching Confidence Routing
        if eval_result.route == "AUTO_LINK" and eval_result.selected_candidate:
            top_cand = eval_result.selected_candidate
            target_activity = db.query(Activity).filter(Activity.id == top_cand.activity_id).first()

            # Check if execution date was missing and not resolved
            date_missing = "[DATE_NEEDED]" in (event.extraction_notes or "")
            if date_missing:
                conv.clarification_turns += 1
                conv.status = "WAITING_FOR_USER"
                data_date_str = project.data_date.strftime("%Y-%m-%d") if project.data_date else "today"
                question = f"Matched to {target_activity.activity_code} ({target_activity.name}). On what date was this work performed? (Project data date is {data_date_str})"
                return cls._save_and_return_agent_response(
                    db=db,
                    conv=conv,
                    reply_text=question,
                    action_card=ActionCardDTO(
                        type="CLARIFICATION_CHOICE",
                        event_id=event.id,
                        activity_id=target_activity.id,
                        activity_code=target_activity.activity_code,
                        question=question,
                        options=[
                            {"label": f"Project Data Date ({data_date_str})", "value": data_date_str},
                            {"label": "Today", "value": "today"},
                            {"label": "Yesterday", "value": "yesterday"},
                        ],
                    ),
                )

            # Check quantity semantics clarification if ambiguous
            if parsed.quantity is not None and parsed.quantity_semantics == "UNKNOWN" and conv.clarification_turns == 0:
                conv.clarification_turns += 1
                conv.status = "WAITING_FOR_USER"
                question = (
                    f"I matched this to {target_activity.activity_code} ({target_activity.name}). "
                    f"Is {parsed.quantity} {parsed.unit or ''} the incremental amount completed today, "
                    f"or the cumulative total completed to date?"
                )
                return cls._save_and_return_agent_response(
                    db=db,
                    conv=conv,
                    reply_text=question,
                    action_card=ActionCardDTO(
                        type="CLARIFICATION_CHOICE",
                        event_id=event.id,
                        activity_id=target_activity.id,
                        activity_code=target_activity.activity_code,
                        question=question,
                        options=[
                            {"label": f"Incremental for today (+{parsed.quantity} {parsed.unit or ''})", "value": "incremental"},
                            {"label": f"Cumulative total to date ({parsed.quantity} {parsed.unit or ''})", "value": "cumulative"},
                        ],
                    ),
                )

            # High confidence match ready for proposal staging!
            prev_pct = target_activity.percent_complete or 0.0
            proposed_pct = prev_pct
            incremental_qty = event.quantity

            if parsed.override_percent is not None:
                proposed_pct = parsed.override_percent
            elif event.quantity is not None and target_activity.planned_quantity and target_activity.planned_quantity > 0:
                q_planned = float(target_activity.planned_quantity)
                if parsed.quantity_semantics == "CUMULATIVE":
                    q_prev = round((prev_pct / 100.0) * q_planned, 4)
                    incremental_qty = round(max(0.0, float(event.quantity) - q_prev), 2)
                    proposed_pct = min(100.0, (float(event.quantity) / q_planned) * 100.0)
                else:
                    qty_ratio = (float(event.quantity) / q_planned) * 100.0
                    proposed_pct = min(100.0, prev_pct + qty_ratio)
            elif event.status_reported == "COMPLETED":
                proposed_pct = 100.0
            else:
                proposed_pct = min(100.0, prev_pct + 25.0 if prev_pct < 75.0 else 100.0)

            proposed_pct = round(proposed_pct, 2)

            # Stage persistent UpdateProposal in PostgreSQL
            proposal = cls.stage_proposal(
                db=db,
                conversation=conv,
                event=event,
                activity=target_activity,
                proposed_percent=proposed_pct,
                proposed_status=target_activity.status,
                quantity_semantics=parsed.quantity_semantics or "INCREMENTAL",
                incremental_quantity=incremental_qty,
                override_percent=parsed.override_percent,
            )

            card = ActionCardDTO(
                type="PROPOSAL_CONFIRMATION",
                proposal_id=proposal.id,
                event_id=event.id,
                activity_id=target_activity.id,
                activity_code=target_activity.activity_code,
                activity_name=target_activity.name,
                current_percent=prev_pct,
                proposed_percent=proposed_pct,
                incremental_quantity=incremental_qty,
                unit=event.unit,
                execution_date=event.execution_date.strftime("%Y-%m-%d"),
            )

            score_pct = int(round(top_cand.match_score * 100))
            delta_note = f" (+{incremental_qty} {event.unit})" if incremental_qty else ""
            reply_text = (
                f"I've matched this to {target_activity.activity_code} ({target_activity.name}) "
                f"with {score_pct}% confidence. This will advance progress from {prev_pct}% to {proposed_pct}%{delta_note}. "
                f"Please confirm to apply this update to the authoritative schedule."
            )

            return cls._save_and_return_agent_response(
                db=db,
                conv=conv,
                reply_text=reply_text,
                action_card=card,
            )

        # Ambiguous Match or Low Confidence Routing
        if conv.clarification_turns >= 3:
            # Clarification limit reached -> route safely to Planner Review queue
            event.status = "IN_REVIEW"
            conv.active_event_id = None
            conv.status = "ACTIVE"
            reply_text = (
                f"I could not resolve this report with high confidence after {conv.clarification_turns} clarification turns. "
                f"I have routed event {event.id} to the Lead Planner Review Queue for manual verification."
            )
            return cls._save_and_return_agent_response(
                db=db,
                conv=conv,
                reply_text=reply_text,
                action_card=None,
            )

        # Formulate candidate-aware targeted clarification question
        conv.clarification_turns += 1
        conv.status = "WAITING_FOR_USER"

        candidates = eval_result.all_candidates
        top_score = candidates[0].match_score if candidates else 0.0

        # Dynamic selection: only present candidates when scores are sufficiently meaningful (>= 0.20)
        if not candidates or top_score < 0.20:
            meaningful_cands = []
        else:
            meaningful_cands = [
                c for c in candidates
                if c.match_score >= 0.25 and c.match_score >= (top_score - 0.25)
            ]
            if len(meaningful_cands) < 2 and len(candidates) >= 2 and candidates[1].match_score >= 0.20:
                meaningful_cands = candidates[:2]
            elif not meaningful_cands and candidates and top_score >= 0.20:
                meaningful_cands = candidates[:1]

        if len(meaningful_cands) == 2:
            c1, c2 = meaningful_cands[0], meaningful_cands[1]
            question = f"Did this work apply to {c1.activity_code} ({c1.activity_name}) or {c2.activity_code} ({c2.activity_name})?"
            options = [
                {
                    "label": f"{c1.activity_code} - {c1.activity_name}",
                    "value": c1.activity_code,
                    "activity_code": c1.activity_code,
                    "activity_name": c1.activity_name,
                    "confidence_score": c1.match_score,
                },
                {
                    "label": f"{c2.activity_code} - {c2.activity_name}",
                    "value": c2.activity_code,
                    "activity_code": c2.activity_code,
                    "activity_name": c2.activity_name,
                    "confidence_score": c2.match_score,
                },
                {
                    "label": "None of these",
                    "value": "NONE_OF_THESE",
                },
            ]
        elif len(meaningful_cands) >= 3:
            slice_cands = meaningful_cands[:4]
            question = "I found several possible activities. Select the activity this update applies to:"
            options = [
                {
                    "label": f"{c.activity_code} - {c.activity_name}",
                    "value": c.activity_code,
                    "activity_code": c.activity_code,
                    "activity_name": c.activity_name,
                    "confidence_score": c.match_score,
                }
                for c in slice_cands
            ]
            options.append({
                "label": "None of these",
                "value": "NONE_OF_THESE",
            })
        elif len(meaningful_cands) == 1:
            c1 = meaningful_cands[0]
            question = f"Did this work apply to {c1.activity_code} ({c1.activity_name})? Please confirm the specific location or foundation."
            options = [
                {
                    "label": f"{c1.activity_code} - {c1.activity_name}",
                    "value": c1.activity_code,
                    "activity_code": c1.activity_code,
                    "activity_name": c1.activity_name,
                    "confidence_score": c1.match_score,
                },
                {
                    "label": "None of these",
                    "value": "NONE_OF_THESE",
                },
            ]
        else:
            desc_cited = parsed.description or raw_text
            question = f"I could not find an activity matching '{desc_cited}' in project {project.name}. Could you please specify which activity code (e.g., CIV-1001) or work package this progress belongs to?"
            options = []

        return cls._save_and_return_agent_response(
            db=db,
            conv=conv,
            reply_text=question,
            action_card=ActionCardDTO(
                type="CLARIFICATION_CHOICE",
                event_id=event.id,
                question=question,
                options=options,
            ),
        )

    @classmethod
    def _save_and_return_agent_response(
        cls,
        db: Session,
        conv: Conversation,
        reply_text: str,
        action_card: Optional[ActionCardDTO],
    ) -> MessageResponseDTO:
        meta_json = json.dumps(action_card.model_dump()) if action_card else None
        agent_msg = ConversationMessage(
            id=f"msg-{uuid.uuid4().hex[:8]}",
            conversation_id=conv.id,
            sender="AGENT",
            content=reply_text,
            message_metadata=meta_json,
        )
        conv.updated_at = datetime.utcnow()
        db.add(agent_msg)
        db.commit()

        return MessageResponseDTO(
            message_id=agent_msg.id,
            sender="AGENT",
            reply_text=reply_text,
            action_card=action_card,
            created_at=agent_msg.created_at.isoformat(),
        )

    @classmethod
    def stage_proposal(
        cls,
        db: Session,
        conversation: Conversation,
        event: ExecutionEvent,
        activity: Activity,
        proposed_percent: float,
        proposed_status: str = "IN_PROGRESS",
        quantity_semantics: str = "INCREMENTAL",
        incremental_quantity: Optional[float] = None,
        override_percent: Optional[float] = None,
        ttl_seconds: int = 300,
    ) -> UpdateProposal:
        proposal = UpdateProposal(
            id=f"prop-{uuid.uuid4().hex[:8]}",
            conversation_id=conversation.id,
            event_id=event.id,
            project_id=conversation.project_id,
            matched_activity_id=activity.id,
            proposed_state=json.dumps({
                "current_percent": activity.percent_complete or 0.0,
                "proposed_percent": proposed_percent,
                "incremental_quantity": incremental_quantity or event.quantity,
                "unit": event.unit,
                "quantity_semantics": quantity_semantics,
                "override_percent": override_percent,
            }),
            baseline_activity_state=json.dumps({
                "percent_complete": activity.percent_complete or 0.0,
                "status": activity.status,
            }),
            status="PENDING",
            expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds),
        )
        db.add(proposal)
        conversation.status = "WAITING_FOR_USER"
        db.flush()
        return proposal

    @classmethod
    def process_attachment(
        cls,
        db: Session,
        project_id: str,
        conversation_id: str,
        file_bytes: bytes,
        filename: str,
        caller_id: str = "site-supervisor",
    ) -> AttachmentResponseDTO:
        conv = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.project_id == project_id)
            .first()
        )
        if not conv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

        # Upload to MinIO using existing MinIO service
        storage_key, file_hash, is_dup = minio_service.upload_artifact(
            project_id=project_id,
            file_bytes=file_bytes,
            filename=filename,
        )

        # Record in artifacts table
        artifact = Artifact(
            id=f"art-{uuid.uuid4().hex[:8]}",
            project_id=project_id,
            filename=f"projects/{project_id}/reports/chat/{filename}",
            original_filename=filename,
            file_type=filename.split(".")[-1].lower() if "." in filename else "bin",
            file_size=len(file_bytes),
            sha256=file_hash,
            storage_bucket="sih-artifacts",
            storage_key=storage_key,
            uploaded_by=caller_id,
            extraction_status="PENDING",
        )
        db.add(artifact)
        db.flush()

        # Call ExtractionService to extract events from document
        extracted_events = ExtractionService.extract_artifact(
            db=db,
            artifact_id=artifact.id,
            force_reextract=True,
        )

        # Bind events to conversation as HYBRID
        for ev in extracted_events:
            ev.conversation_id = conv.id
            ev.source_type = "HYBRID"
        db.flush()

        if extracted_events:
            first_event = extracted_events[0]
            conv.active_event_id = first_event.id
            conv.clarification_turns = 0
            db.flush()

            # Evaluate match
            eval_res = MatchingService.evaluate_event_for_agent(db, first_event)
            if eval_res.route == "AUTO_LINK" and eval_res.selected_candidate:
                top_c = eval_res.selected_candidate
                act = db.query(Activity).filter(Activity.id == top_c.activity_id).first()

                prev_pct = act.percent_complete or 0.0
                proposed_pct = min(100.0, prev_pct + 25.0 if prev_pct < 75.0 else 100.0)
                if first_event.quantity and act.planned_quantity and act.planned_quantity > 0:
                    proposed_pct = min(100.0, prev_pct + (first_event.quantity / act.planned_quantity) * 100.0)
                proposed_pct = round(proposed_pct, 2)

                proposal = UpdateProposal(
                    id=f"prop-{uuid.uuid4().hex[:8]}",
                    conversation_id=conv.id,
                    event_id=first_event.id,
                    project_id=project_id,
                    matched_activity_id=act.id,
                    proposed_state=json.dumps({
                        "current_percent": prev_pct,
                        "proposed_percent": proposed_pct,
                        "incremental_quantity": first_event.quantity,
                        "unit": first_event.unit,
                    }),
                    baseline_activity_state=json.dumps({
                        "percent_complete": act.percent_complete,
                        "status": act.status,
                    }),
                    status="PENDING",
                    expires_at=datetime.utcnow() + timedelta(seconds=300),
                )
                db.add(proposal)
                db.commit()

                card = ActionCardDTO(
                    type="PROPOSAL_CONFIRMATION",
                    proposal_id=proposal.id,
                    event_id=first_event.id,
                    activity_id=act.id,
                    activity_code=act.activity_code,
                    activity_name=act.name,
                    current_percent=prev_pct,
                    proposed_percent=proposed_pct,
                    incremental_quantity=first_event.quantity,
                    unit=first_event.unit,
                    execution_date=first_event.execution_date.strftime("%Y-%m-%d"),
                )
                agent_text = (
                    f"Processed {filename} and extracted {len(extracted_events)} event(s). "
                    f"Matched to {act.activity_code} ({act.name}). Ready for your confirmation."
                )
            else:
                db.commit()
                agent_text = (
                    f"Processed {filename} and extracted {len(extracted_events)} event(s). "
                    f"The top candidate match is ambiguous. Which specific foundation or work package was performed?"
                )
                card = None
        else:
            db.commit()
            agent_text = f"Processed {filename}, but no physical construction progress events were detected."
            card = None

        return AttachmentResponseDTO(
            artifact_id=artifact.id,
            filename=filename,
            extracted_events_count=len(extracted_events),
            agent_message=agent_text,
            action_card=card,
        )

    @classmethod
    def confirm_proposal(
        cls,
        db: Session,
        project_id: str,
        conversation_id: str,
        proposal_id: str,
        caller_id: str = "site-supervisor",
    ) -> ProposalConfirmResponse:
        """
        Executes an atomic, row-locked confirmation transaction:
        1. Acquires SELECT FOR UPDATE on update_proposals
        2. Validates project/conversation/event scope invariants
        3. Verifies TTL and baseline activity state
        4. Invokes ScheduleUpdateService.apply_event_progress(commit=False)
        5. Updates proposal status to CONSUMED and event status to APPLIED
        6. Single atomic commit
        """
        # 1. Acquire row lock within active transaction
        proposal_query = (
            db.query(UpdateProposal)
            .filter(
                UpdateProposal.id == proposal_id,
                UpdateProposal.conversation_id == conversation_id,
                UpdateProposal.project_id == project_id,
            )
        )
        # In SQLite (unit tests), with_for_update is ignored or not supported, in PostgreSQL it locks the row
        if not db.bind.name.startswith("sqlite"):
            proposal_query = proposal_query.with_for_update()

        proposal = proposal_query.first()
        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proposal {proposal_id} not found in this conversation.",
            )

        # 2. Check proposal status
        if proposal.status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Proposal already {proposal.status.lower()} (PROPOSAL_ALREADY_CONSUMED).",
            )

        # 3. Check expiration
        if datetime.utcnow() > proposal.expires_at:
            proposal.status = "EXPIRED"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Proposal has expired (PROPOSAL_EXPIRED). Please submit a new report.",
            )

        # 4. Scope and entity verification
        event = db.query(ExecutionEvent).filter(ExecutionEvent.id == proposal.event_id).first()
        if not event or event.project_id != project_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-project entity violation.")

        activity = db.query(Activity).filter(Activity.id == proposal.matched_activity_id).first()
        if not activity or activity.project_id != project_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-project activity violation.")

        # 5. Stale baseline concurrency check
        baseline = json.loads(proposal.baseline_activity_state)
        current_pct = activity.percent_complete or 0.0
        baseline_pct = baseline.get("percent_complete") or 0.0
        if round(current_pct, 2) != round(baseline_pct, 2) or activity.status != baseline.get("status"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Activity baseline state modified concurrently (STALE_ACTIVITY_BASELINE).",
            )

        # 6. Execute atomic schedule mutation inside caller transaction
        try:
            proposal.status = "CONFIRMED"
            proposal.confirmed_by = caller_id
            proposal.confirmed_at = datetime.utcnow()

            proposed_data = json.loads(proposal.proposed_state)
            override_pct = proposed_data.get("override_percent")
            target_proposed = proposed_data.get("proposed_percent")
            eff_override = override_pct if override_pct is not None else target_proposed

            updated_act = ScheduleUpdateService.apply_event_progress(
                db=db,
                event_id=proposal.event_id,
                activity_id=proposal.matched_activity_id,
                user_id=caller_id,
                override_percent=eff_override,
                action_name="TIME_AGENT_CONVERSATIONAL_UPDATE",
                quantity_semantics=proposed_data.get("quantity_semantics", "INCREMENTAL"),
                commit=False,  # Single unified commit owned by this method
            )

            proposal.status = "CONSUMED"
            proposal.consumed_at = datetime.utcnow()

            # Clear active event from conversation
            conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            if conv:
                conv.active_event_id = None
                conv.status = "RESOLVED"

            # Fetch audit log ID
            audit_entry = (
                db.query(ScheduleAuditLog)
                .filter(
                    ScheduleAuditLog.activity_id == activity.id,
                    ScheduleAuditLog.execution_event_id == event.id,
                )
                .order_by(ScheduleAuditLog.timestamp.desc())
                .first()
            )
            audit_id = audit_entry.id if audit_entry else "audit-recorded"

            db.commit()
            db.refresh(updated_act)

            return ProposalConfirmResponse(
                status="APPLIED",
                activity_id=updated_act.id,
                activity_code=updated_act.activity_code,
                previous_percent=baseline_pct,
                new_percent=updated_act.percent_complete,
                audit_log_id=audit_id,
                message=f"{updated_act.activity_code} successfully updated to {updated_act.percent_complete}%.",
            )
        except ValidationException as ve:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
        except Exception as e:
            db.rollback()
            logger.error(f"Error during proposal confirmation: {e}")
            raise

    @classmethod
    def confirm_bulk_proposal(
        cls,
        db: Session,
        project_id: str,
        conversation_id: str,
        payload: BulkProposalConfirmRequest,
        caller_id: str = "site-supervisor",
    ) -> BulkProposalConfirmResponse:
        conv = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.project_id == project_id)
            .first()
        )
        if not conv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

        if payload.action == "CANCEL":
            conv.active_event_id = None
            conv.status = "ACTIVE"

            # Mark prior bulk proposal message as CANCELLED
            prior_msgs = (
                db.query(ConversationMessage)
                .filter(ConversationMessage.conversation_id == conv.id, ConversationMessage.sender == "AGENT")
                .all()
            )
            for m in prior_msgs:
                if m.message_metadata:
                    try:
                        meta = json.loads(m.message_metadata) if isinstance(m.message_metadata, str) else m.message_metadata
                        if meta.get("type") == "BULK_SCOPE_PROPOSAL":
                            meta["proposal_status"] = "CANCELLED"
                            m.message_metadata = json.dumps(meta)
                    except Exception:
                        pass

            cancel_msg = ConversationMessage(
                id=f"msg-{uuid.uuid4().hex[:8]}",
                conversation_id=conv.id,
                sender="AGENT",
                content="Bulk update cancelled by user. No schedule mutations were applied.",
            )
            db.add(cancel_msg)
            db.commit()
            return BulkProposalConfirmResponse(
                status="CANCELLED",
                updated_count=0,
                updated_activities=[],
                message="Bulk update cancelled by user.",
            )

        act_query = db.query(Activity).filter(Activity.project_id == project_id)
        if payload.activity_ids:
            act_query = act_query.filter(Activity.id.in_(payload.activity_ids))
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No activity IDs provided for bulk update.")

        target_acts = act_query.all()
        if not target_acts:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No matching activities found.")

        target_pct = payload.target_percent if payload.target_percent is not None else 100.0
        updated_records = []

        try:
            for act in target_acts:
                ev = ExecutionEvent(
                    id=f"ev-{uuid.uuid4().hex[:8]}",
                    project_id=project_id,
                    source_type="CONVERSATION",
                    conversation_id=conv.id,
                    verbatim_excerpt=f"Bulk update {act.activity_code} to {target_pct}%",
                    description=f"Bulk progress update to {target_pct}% complete",
                    reported_activity_code=act.activity_code,
                    execution_date=datetime.utcnow(),
                    status_reported=payload.status_reported or "COMPLETED",
                    extraction_confidence=1.0,
                    status="AUTO_LINKED",
                )
                db.add(ev)
                db.flush()

                prev_pct = act.percent_complete or 0.0
                updated_act = ScheduleUpdateService.apply_event_progress(
                    db=db,
                    event_id=ev.id,
                    activity_id=act.id,
                    user_id=caller_id,
                    override_percent=target_pct,
                    action_name="TIME_AGENT_BULK_UPDATE",
                    quantity_semantics="INCREMENTAL",
                    commit=False,
                )
                updated_records.append({
                    "activity_id": updated_act.id,
                    "activity_code": updated_act.activity_code,
                    "previous_percent": prev_pct,
                    "new_percent": updated_act.percent_complete,
                    "status": updated_act.status,
                })

            conv.active_event_id = None
            conv.status = "RESOLVED"
            conv.updated_at = datetime.utcnow()

            # Mark prior bulk proposal card as APPLIED
            prior_msgs = (
                db.query(ConversationMessage)
                .filter(ConversationMessage.conversation_id == conv.id, ConversationMessage.sender == "AGENT")
                .all()
            )
            for m in prior_msgs:
                if m.message_metadata:
                    try:
                        meta = json.loads(m.message_metadata) if isinstance(m.message_metadata, str) else m.message_metadata
                        if meta.get("type") == "BULK_SCOPE_PROPOSAL":
                            meta["proposal_status"] = "APPLIED"
                            m.message_metadata = json.dumps(meta)
                    except Exception:
                        pass

            summary_codes = ", ".join([r["activity_code"] for r in updated_records])
            confirm_msg = ConversationMessage(
                id=f"msg-{uuid.uuid4().hex[:8]}",
                conversation_id=conv.id,
                sender="AGENT",
                content=f"Successfully updated {len(updated_records)} activities to {target_pct}% complete: {summary_codes}. Ledger audit records created and schedule refreshed.",
            )
            db.add(confirm_msg)
            db.commit()

            return BulkProposalConfirmResponse(
                status="APPLIED",
                updated_count=len(updated_records),
                updated_activities=updated_records,
                message=f"Applied bulk update to {len(updated_records)} activities.",
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Bulk update failed: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
