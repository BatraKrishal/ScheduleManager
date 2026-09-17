from __future__ import annotations

from typing import Dict, List, Optional
from app.models.canonical import (
    ActivityStatus,
    CanonicalActivity,
    CanonicalProject,
    CanonicalRelationship,
    CanonicalSchedule,
    CanonicalWBSNode,
    RelationshipType,
)
from app.parsers.base import BaseParser, ParserError


class XerParser(BaseParser):
    def parse(self, content: bytes, filename: str) -> CanonicalSchedule:
        try:
            text = content.decode("utf-8", errors="replace")
        except Exception as e:
            raise ParserError(f"Failed to decode XER file: {str(e)}")

        tables: Dict[str, List[Dict[str, str]]] = {}
        current_table: Optional[str] = None
        fields: Optional[List[str]] = None

        lines = text.splitlines()
        if not lines:
            raise ParserError("Empty XER file")

        # Basic XER header verification
        first_line = lines[0].strip()
        if not (first_line.startswith("ERMHDR") or "%T" in text):
            raise ParserError("Invalid XER format: Missing ERMHDR or table markers")

        for line in lines:
            line = line.rstrip("\r\n")
            if not line:
                continue
            parts = line.split("\t")
            tag = parts[0]

            if tag == "%T":
                if len(parts) > 1:
                    current_table = parts[1].strip()
                    tables[current_table] = []
                    fields = None
            elif tag == "%F":
                fields = [f.strip() for f in parts[1:]]
            elif tag == "%R" and current_table and fields:
                vals = parts[1:]
                # Pad values if shorter than field count
                if len(vals) < len(fields):
                    vals = vals + [""] * (len(fields) - len(vals))
                row_dict = dict(zip(fields, vals[:len(fields)]))
                tables[current_table].append(row_dict)
            elif tag == "%E":
                break

        # 1. Parse Project
        project_rows = tables.get("PROJECT", [])
        if project_rows:
            p_row = project_rows[0]
            proj_code = p_row.get("proj_short_name") or filename.rsplit(".", 1)[0]
            proj_name = p_row.get("proj_short_name") or p_row.get("project_name") or proj_code
            plan_start = self.parse_datetime(p_row.get("plan_start_date") or p_row.get("target_start_date"))
            plan_finish = self.parse_datetime(p_row.get("plan_end_date") or p_row.get("target_end_date"))
            data_date = self.parse_datetime(p_row.get("last_recalc_date") or p_row.get("scd_end_date"))
        else:
            proj_code = filename.rsplit(".", 1)[0]
            proj_name = proj_code
            plan_start, plan_finish, data_date = None, None, None

        canonical_project = CanonicalProject(
            project_code=proj_code.strip(),
            name=proj_name.strip(),
            planned_start=plan_start,
            planned_finish=plan_finish,
            data_date=data_date,
        )

        # 2. Parse WBS
        wbs_rows = tables.get("PROJWBS", [])
        wbs_id_to_code: Dict[str, str] = {}
        wbs_id_to_parent_id: Dict[str, Optional[str]] = {}
        canonical_wbs_list: List[CanonicalWBSNode] = []

        for row in wbs_rows:
            wbs_id = row.get("wbs_id", "").strip()
            if not wbs_id:
                continue
            wbs_short = row.get("wbs_short_name", "").strip()
            wbs_name = row.get("wbs_name", "").strip() or wbs_short or f"WBS-{wbs_id}"
            code = wbs_short if wbs_short else f"WBS-{wbs_id}"
            wbs_id_to_code[wbs_id] = code
            parent_id = row.get("parent_wbs_id", "").strip() or None
            wbs_id_to_parent_id[wbs_id] = parent_id

        # Resolve parent_code for WBS nodes
        for row in wbs_rows:
            wbs_id = row.get("wbs_id", "").strip()
            if not wbs_id:
                continue
            code = wbs_id_to_code[wbs_id]
            wbs_name = row.get("wbs_name", "").strip() or row.get("wbs_short_name", "").strip() or code
            parent_id = wbs_id_to_parent_id.get(wbs_id)
            parent_code = wbs_id_to_code.get(parent_id) if parent_id and parent_id != wbs_id else None

            canonical_wbs_list.append(
                CanonicalWBSNode(
                    code=code,
                    name=wbs_name,
                    parent_code=parent_code,
                    wbs_id=wbs_id,
                )
            )

        # 3. Parse Activities
        task_rows = tables.get("TASK", [])
        task_id_to_code: Dict[str, str] = {}
        canonical_activities: List[CanonicalActivity] = []

        for row in task_rows:
            task_id = row.get("task_id", "").strip()
            task_code = row.get("task_code", "").strip() or f"ACT-{task_id}"
            if task_id:
                task_id_to_code[task_id] = task_code

            task_name = row.get("task_name", "").strip() or task_code
            wbs_id = row.get("wbs_id", "").strip()
            wbs_code = wbs_id_to_code.get(wbs_id) if wbs_id else None

            # Status mapping
            raw_status = row.get("status_code", "").strip()
            if raw_status == "TK_Complete":
                status = ActivityStatus.COMPLETED
                pct = 100.0
            elif raw_status == "TK_Active":
                status = ActivityStatus.IN_PROGRESS
                pct = self.parse_float(row.get("phys_percent_comp"), default=50.0)
            else:
                status = ActivityStatus.NOT_STARTED
                pct = self.parse_float(row.get("phys_percent_comp"), default=0.0)

            # Dates
            plan_start = self.parse_datetime(row.get("target_start_date") or row.get("early_start_date"))
            plan_finish = self.parse_datetime(row.get("target_end_date") or row.get("early_end_date"))
            act_start = self.parse_datetime(row.get("act_start_date"))
            act_finish = self.parse_datetime(row.get("act_end_date"))

            # Duration: P6 stores hours (standard 8hr/day)
            target_hr = self.parse_float(row.get("target_drtn_hr_cnt"))
            remain_hr = self.parse_float(row.get("remain_drtn_hr_cnt"))
            orig_dur = round(target_hr / 8.0, 2) if target_hr is not None else None
            rem_dur = round(remain_hr / 8.0, 2) if remain_hr is not None else orig_dur

            canonical_activities.append(
                CanonicalActivity(
                    activity_code=task_code,
                    name=task_name,
                    wbs_code=wbs_code,
                    activity_type=row.get("task_type") or "TT_Task",
                    status=status,
                    planned_start=plan_start,
                    planned_finish=plan_finish,
                    actual_start=act_start,
                    actual_finish=act_finish,
                    original_duration=orig_dur,
                    remaining_duration=rem_dur,
                    percent_complete=pct,
                    calendar=row.get("clndr_id"),
                )
            )

        # 4. Parse Relationships
        pred_rows = tables.get("TASKPRED", [])
        canonical_relationships: List[CanonicalRelationship] = []

        type_map = {
            "PR_FS": RelationshipType.FS,
            "PR_SS": RelationshipType.SS,
            "PR_FF": RelationshipType.FF,
            "PR_SF": RelationshipType.SF,
            "FS": RelationshipType.FS,
            "SS": RelationshipType.SS,
            "FF": RelationshipType.FF,
            "SF": RelationshipType.SF,
        }

        for row in pred_rows:
            task_id = row.get("task_id", "").strip()
            pred_id = row.get("pred_task_id", "").strip()

            # P6 TASKPRED: task_id is the SUCCESSOR, pred_task_id is the PREDECESSOR
            succ_code = task_id_to_code.get(task_id) or task_id
            pred_code = task_id_to_code.get(pred_id) or pred_id

            if not succ_code or not pred_code:
                continue

            raw_rel = row.get("pred_type", "PR_FS").strip()
            rel_type = type_map.get(raw_rel, RelationshipType.FS)

            lag_hr = self.parse_float(row.get("lag_hr_cnt"), default=0.0)
            lag_days = round((lag_hr or 0.0) / 8.0, 2)

            canonical_relationships.append(
                CanonicalRelationship(
                    predecessor_code=pred_code,
                    successor_code=succ_code,
                    relationship_type=rel_type,
                    lag=lag_days,
                )
            )

        return CanonicalSchedule(
            project=canonical_project,
            wbs=canonical_wbs_list,
            activities=canonical_activities,
            relationships=canonical_relationships,
        )
