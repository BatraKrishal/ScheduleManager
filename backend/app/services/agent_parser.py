from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import httpx

from app.schemas.agent import ParsedConversationalIntent
from app.services.credential_resolver import CredentialResolver
from app.services.extraction_service import ExtractionService

logger = logging.getLogger("agent_parser")


class ConversationalParser:
    """
    Parses conversational user utterances into structured intent and execution-event fields
    using Google Gemini API via TIME_AGENT_GEMINI_API_KEY (with governed fallback),
    with deterministic date resolution and offline rule-based fallbacks.
    """

    WEEKDAYS = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    def __init__(self, gemini_api_key: Optional[str] = None):
        res = CredentialResolver.resolve_time_agent_credentials(explicit_key=gemini_api_key)
        self.gemini_api_key = res.api_key
        self.model = res.model
        self.credential_source = res.source

    def parse(
        self,
        text: str,
        reference_date: Optional[datetime] = None,
        active_activity_code: Optional[str] = None,
        is_clarification_turn: bool = False,
    ) -> ParsedConversationalIntent:
        return self.parse_message(
            text=text,
            project_data_date=reference_date,
            active_activity_code=active_activity_code,
            is_clarification_turn=is_clarification_turn,
        )

    @classmethod
    def resolve_date(
        cls,
        raw_date_str: Optional[str],
        reference_date: Optional[datetime] = None,
    ) -> Optional[datetime]:
        """
        Deterministically resolves natural language temporal references against reference_date
        (defaults to project.data_date, or current UTC date if project.data_date is null).
        Prevents silent defaulting to current calendar date when reporting against past schedules.
        """
        if not raw_date_str:
            return None

        clean = raw_date_str.strip().lower()
        ref = reference_date or datetime.utcnow()

        # ISO format: YYYY-MM-DD
        iso_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", clean)
        if iso_match:
            try:
                return datetime.strptime(iso_match.group(0), "%Y-%m-%d")
            except ValueError:
                pass

        if "today" in clean:
            return datetime(ref.year, ref.month, ref.day)

        if "yesterday" in clean:
            y = ref - timedelta(days=1)
            return datetime(y.year, y.month, y.day)

        # Check day names (e.g. "on monday")
        for day_name, day_idx in cls.WEEKDAYS.items():
            if day_name in clean:
                ref_day = ref.weekday()
                delta_days = (ref_day - day_idx) % 7
                if delta_days == 0:
                    delta_days = 7  # Most recent prior occurrence
                resolved_day = ref - timedelta(days=delta_days)
                return datetime(resolved_day.year, resolved_day.month, resolved_day.day)

        return None

    @classmethod
    def parse_with_gemini(
        cls,
        text: str,
        project_data_date_str: str = "",
        active_activity_code: Optional[str] = None,
        is_clarification_turn: bool = False,
    ) -> Optional[ParsedConversationalIntent]:
        """
        Calls Google Gemini API using GEMINI_API_KEY with strict schema constraint.
        """
        res = CredentialResolver.resolve_time_agent_credentials()
        gemini_api_key = res.api_key
        if not gemini_api_key:
            return None

        prompt = f"""You are an authoritative construction execution agent.
Parse the following user message into a structured JSON execution event representation.

Project reference data date: {project_data_date_str or 'Not Specified'}
Currently active activity anchor in UI: {active_activity_code or 'None'}
Is currently in clarification dialog: {is_clarification_turn}

Classify into EXACTLY one of these intents:
- INFORMATION_QUERY: Supervisor asks about schedule, activity details, duration, dates, or progress.
- PROGRESS_REPORT: Supervisor describes physical construction work completed or underway.
- PROGRESS_UPDATE_REQUEST: Supervisor directly requests a percentage or status change (e.g. "update this to 80%").
- CLARIFICATION_RESPONSE: Supervisor provides missing information in direct response to an agent question (e.g. "F-204", "incremental").
- ARTIFACT_SUBMISSION: Supervisor uploads or references a file attachment.

Extract the following fields if present in the message:
- quantity: numerical float or null
- unit: standard engineering unit (m3, m2, t, m, ea) or null
- quantity_semantics: INCREMENTAL (work done today/this shift), CUMULATIVE (total work completed to date), or UNKNOWN
- location: physical structural element or area (e.g. Foundation F-204, Pier 14, Level 2) or null
- discipline: engineering discipline (Civil, Structural, Piping, Electrical, Mechanical) or null
- contractor: subcontractor or crew name or null
- asset: equipment or tag code or null
- wbs_hint: work package or WBS hint or null
- reported_activity_code: explicit activity code cited in text (e.g. CIV-1001, STR-204); do NOT guess
- execution_date: date mentioned in text (e.g. '2024-09-30', 'today', 'yesterday', 'Monday') or null if no date cited
- status_reported: COMPLETED, IN_PROGRESS, or NOT_STARTED
- override_percent: numerical float percentage (0-100) if explicitly stated; otherwise null
- description: concise summary of work described

Return ONLY valid JSON matching this structure:
{{
  "intent": "PROGRESS_REPORT",
  "confidence": 0.95,
  "entities_present": ["quantity", "unit", "location"],
  "quantity": 35.0,
  "unit": "m3",
  "quantity_semantics": "INCREMENTAL",
  "location": "F-204",
  "discipline": "Civil",
  "contractor": null,
  "asset": null,
  "wbs_hint": null,
  "reported_activity_code": null,
  "execution_date": "today",
  "status_reported": "IN_PROGRESS",
  "override_percent": null,
  "description": "Poured 35 cubic meters of concrete for F-204"
}}

USER MESSAGE:
{text}
"""
        models_to_try = [
            res.model,
            "gemini-2.5-flash",
            "gemini-1.5-flash",
            "gemini-2.0-flash",
        ]
        unique_models = []
        for m in models_to_try:
            if m and m not in unique_models:
                unique_models.append(m)

        for model in unique_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            headers = {
                "x-goog-api-key": gemini_api_key,
                "Content-Type": "application/json",
            }
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.1,
                },
            }
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            raw_json = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
                            parsed = json.loads(raw_json)
                            # Normalize unit
                            if parsed.get("unit"):
                                parsed["unit"] = ExtractionService.normalize_unit(parsed["unit"])
                            # Normalize status
                            parsed["status_reported"] = ExtractionService.normalize_status(parsed.get("status_reported"))
                            return ParsedConversationalIntent(**parsed)
                    else:
                        logger.warning(f"Gemini model {model} returned HTTP {resp.status_code}")
            except Exception as e:
                logger.warning(f"Gemini API call to {model} failed: {e}")

        return None

    @classmethod
    def parse_with_rules(
        cls,
        text: str,
        reference_date: Optional[datetime] = None,
        active_activity_code: Optional[str] = None,
        is_clarification_turn: bool = False,
    ) -> ParsedConversationalIntent:
        """
        Rule-based parser fallback ensuring 100% deterministic and reliable offline execution.
        """
        t = text.strip()
        lower = t.lower()
        entities_present = []

        # 1. Intent determination
        if lower.startswith(("what", "who", "when", "how", "show", "is there", "details of")):
            intent = "INFORMATION_QUERY"
        elif "uploaded" in lower or "attached" in lower or lower.endswith((".pdf", ".xlsx", ".csv")):
            intent = "ARTIFACT_SUBMISSION"
        elif is_clarification_turn and len(t.split()) <= 6:
            intent = "CLARIFICATION_RESPONSE"
        elif re.search(r"\b(?:update|set|mark)\b.*(?:to\s+\d+%|\bcomplete\b)", lower):
            intent = "PROGRESS_UPDATE_REQUEST"
        elif any(verb in lower for verb in ["pour", "poured", "install", "installed", "erect", "erected", "excavat", "placed", "laid", "welded", "completed"]):
            intent = "PROGRESS_REPORT"
        else:
            intent = "PROGRESS_REPORT" if any(c.isdigit() for c in t) else "INFORMATION_QUERY"

        # 2. Activity code extraction (e.g. CIV-1001, STR-1001, ACT-100)
        code_match = re.search(r"\b([A-Z]{2,4}-\d{3,5})\b", t)
        reported_code = code_match.group(1) if code_match else None
        if reported_code:
            entities_present.append("activity_code")

        # 3. Direct percentage override
        pct_match = re.search(r"\b(\d+(?:\.\d+)?)\s*%", t)
        override_percent = float(pct_match.group(1)) if pct_match else None
        if override_percent is not None:
            entities_present.append("override_percent")

        # 4. Quantity and Unit extraction
        qty = None
        unit = None
        qty_match = re.search(
            r"\b(\d+(?:\.\d+)?)\s*(cubic meters?|m3|cum|cu\.m|square meters?|m2|sqm|tonnes?|tons?|t|meters?|mtr|m|nos|ea|each)\b",
            lower,
        )
        if qty_match:
            qty = float(qty_match.group(1))
            unit = ExtractionService.normalize_unit(qty_match.group(2))
            entities_present.extend(["quantity", "unit"])
        else:
            # Standalone quantity: strip activity codes and dates first so their numbers aren't confused with quantities
            text_no_code = re.sub(r"\b[A-Za-z]{1,5}-\d{2,6}\b", "", t)
            text_no_code = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", text_no_code)
            stand_qty = re.search(r"\b(\d+(?:\.\d+)?)\b", text_no_code)
            if stand_qty and intent in ("PROGRESS_REPORT", "CLARIFICATION_RESPONSE"):
                try:
                    val = float(stand_qty.group(1))
                    if val != override_percent:
                        qty = val
                        entities_present.append("quantity")
                except ValueError:
                    pass

        # 5. Quantity Semantics
        if any(term in lower for term in ["cumulative", "total to date", "total so far", "in total"]):
            quantity_semantics = "CUMULATIVE"
        elif any(term in lower for term in ["today", "incremental", "this shift", "additional", "more"]):
            quantity_semantics = "INCREMENTAL"
        else:
            quantity_semantics = "UNKNOWN"

        clean_t = t.strip().rstrip(".,;:!?")
        loc_match = re.search(r"\b(?:for|at|in|on)\s+([A-Z0-9]+-[A-Z0-9]+|Pier\s+\d+|Foundation\s+[A-Z0-9-]+|Level\s+\d+)\b", t, re.IGNORECASE)
        location = loc_match.group(1) if loc_match else None
        if not location:
            # Standalone code in clarification (e.g. "F-204" or "CIV-1001")
            standalone_loc = re.match(r"^([A-Z0-9]+-[A-Z0-9]+)$", clean_t, re.IGNORECASE)
            if standalone_loc:
                val = standalone_loc.group(1).upper()
                if val.startswith("CIV-") or val.startswith("STR-") or val.startswith("PIP-") or val.startswith("ELE-") or val.startswith("INS-"):
                    if not reported_code:
                        reported_code = val
                else:
                    location = val
        if location:
            entities_present.append("location")

        # 7. Discipline extraction
        discipline = None
        if any(d in lower for d in ["concrete", "excavat", "earthwork", "foundation", "civil"]):
            discipline = "Civil"
        elif any(d in lower for d in ["steel", "erect", "beam", "column", "structural"]):
            discipline = "Structural"
        elif any(d in lower for d in ["pipe", "piping", "spool"]):
            discipline = "Piping"
        elif any(d in lower for d in ["cable", "tray", "electric", "power", "switchgear"]):
            discipline = "Electrical"
        elif any(d in lower for d in ["instrument", "sensor", "transmitter"]):
            discipline = "Instrumentation"
        if discipline:
            entities_present.append("discipline")

        # 8. Execution Date extraction
        raw_date = None
        if "today" in lower:
            raw_date = "today"
        elif "yesterday" in lower:
            raw_date = "yesterday"
        else:
            date_m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", t)
            if date_m:
                raw_date = date_m.group(1)
            else:
                for w in cls.WEEKDAYS:
                    if w in lower:
                        raw_date = w
                        break
        if raw_date:
            entities_present.append("execution_date")

        # 9. Status reported
        if any(w in lower for w in ["finish", "finished", "complete", "completed", "done", "100%"]):
            status_reported = "COMPLETED"
        else:
            status_reported = "IN_PROGRESS"

        return ParsedConversationalIntent(
            intent=intent,
            confidence=0.88 if intent != "INFORMATION_QUERY" else 0.95,
            entities_present=entities_present,
            quantity=qty,
            unit=unit,
            quantity_semantics=quantity_semantics,
            location=location,
            discipline=discipline,
            contractor=None,
            asset=None,
            wbs_hint=None,
            reported_activity_code=reported_code,
            execution_date=raw_date,
            status_reported=status_reported,
            override_percent=override_percent,
            description=t,
        )

    @classmethod
    def parse_message(
        cls,
        text: str,
        project_data_date: Optional[datetime] = None,
        active_activity_code: Optional[str] = None,
        is_clarification_turn: bool = False,
    ) -> ParsedConversationalIntent:
        """
        Primary entry point: Attempts Gemini structured extraction, falling back to rules.
        """
        ref_date_str = project_data_date.strftime("%Y-%m-%d") if project_data_date else ""
        parsed = cls.parse_with_gemini(
            text=text,
            project_data_date_str=ref_date_str,
            active_activity_code=active_activity_code,
            is_clarification_turn=is_clarification_turn,
        )
        if not parsed:
            parsed = cls.parse_with_rules(
                text=text,
                reference_date=project_data_date,
                active_activity_code=active_activity_code,
                is_clarification_turn=is_clarification_turn,
            )
        return parsed
