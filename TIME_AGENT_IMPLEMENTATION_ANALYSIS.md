# TIME AGENT IMPLEMENTATION ANALYSIS
## Conversational Execution-Reporting Agent Architecture for ScheduleManager

---

## 1. Executive Summary

This document provides a comprehensive architectural specification and implementation blueprint for the **Time Agent** in the **ScheduleManager** project.

### Core Vision
The **Time Agent** is an intelligent, conversational execution-reporting agent that bridges the gap between site supervisors in the field and the authoritative Critical Path Method (CPM) project schedule. It is **not** a general-purpose knowledge chatbot; it is an active conversational interface designed to extract, clarify, match, and govern execution progress updates.

```
MODE A: ARTIFACT-BASED                  MODE B: CONVERSATIONAL
  Field Report (PDF/XLSX/Audio)            Supervisor Text / Speech
              │                                      │
              ▼                                      ▼
     MinIO Object Storage                   Conversational Parser
              │                                      │
              ▼                                      ▼
    ExtractionService                       Draft ExecutionEvent
              │                                      │
              └───────────────────┬──────────────────┘
                                  │
                                  ▼
                    Unified ExecutionEvent (DRAFT)
                                  │
                                  ▼
                   Candidate Retrieval & Matching
                     (Existing MatchingService)
                                  │
                                  ▼
                     Match-Aware Gap Analysis
                                  │
               ┌──────────────────┴──────────────────┐
               ▼                                     ▼
         HIGH CONFIDENCE                     AMBIGUOUS / MISSING
     (S_total >= 0.85, Delta >= 0.15)       (Multiple candidates, missing data)
               │                                     │
               ▼                                     ▼
      Confirmation Card                    Targeted Clarification Question
      "Update CIV-1001 to 80%?"                      │
               │                                     ▼
               │                              Supervisor Answers
               │                                     │
               │                              Event Enrichment
               │                                     │
               │                              Re-Run Matching
               │                                     │
               └──────────────────┬──────────────────┘
                                  │ (Confirmed)
                                  ▼
                      Governed Schedule Update
                  (Existing ScheduleUpdateService)
                                  │
                                  ▼
                      ActualProgressLedger (Audit)
                                  │
                                  ▼
                     Authoritative Schedule State
                       (Gantt / P6 XER Export)
```

### Architectural Guarantees
1. **Convergence**: Both artifact uploads (Mode A) and conversational reports (Mode B) converge into the **same** structured `ExecutionEvent` representation.
2. **Re-use of Authoritative Engine**: Matching is handled exclusively by the existing [`MatchingService`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/services/matching_service.py), and schedule mutations are executed exclusively by [`ScheduleUpdateService`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/services/schedule_update_service.py).
3. **Match-Aware Clarification**: The agent generates targeted questions derived from actual feature divergence between top candidates (e.g. distinguishing foundation F-204 from F-205) rather than asking generic form-like questions.
4. **CPM Baseline Protection**: Planned dates, durations, WBS tree, and logic links remain strictly immutable during conversational progress updates.
5. **Full Auditability**: Conversational turns, draft events, candidate scores, and supervisor confirmation are logged in [`ScheduleAuditLog`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/domain/models.py) with the same rigor as document-based updates.

---

## 2. Existing ScheduleManager Capabilities

`[EXISTING]` The existing ScheduleManager platform provides a robust foundation for this feature:

| Component | Implementation File | Current Capability | Reusability for Time Agent |
|---|---|---|---|
| **Domain Models** | [`backend/app/domain/models.py`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/domain/models.py) | `Project`, `WBSNode`, `Activity`, `ActivityRelationship`, `Artifact`, `ExecutionEvent`, `ReviewDecision`, `ActualProgressLedger`, `ScheduleAuditLog`, `DomainOutbox`. | Direct re-use. All core schedule and audit entities already exist. |
| **Object Storage** | [`backend/app/services/minio_service.py`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/services/minio_service.py) | MinIO S3 client, SHA-256 duplicate detection, deterministic storage keys, presigned URLs. | Direct re-use for chat attachments and conversation transcripts. |
| **Extraction Engine** | [`backend/app/services/extraction_service.py`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/services/extraction_service.py) | LLM extraction (Gemini / OpenAI), unit normalization (`normalize_unit`), status normalization (`normalize_status`), confidence scoring ($C_{\text{ext}}$). | Direct re-use for parsing natural language and uploaded field attachments. |
| **Matching & Routing** | [`backend/app/services/matching_service.py`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/services/matching_service.py) | Candidate retrieval, 5-signal scoring ($S_{\text{id}}, S_{\text{text}}, S_{\text{wbs}}, S_{\text{temp}}, S_{\text{context}}$), margin delta ($\Delta$), confidence routing. | Direct re-use for scoring draft conversational events and identifying missing information. |
| **Schedule Update** | [`backend/app/services/schedule_update_service.py`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/services/schedule_update_service.py) | Idempotent ledger updates, bounded progress calculation, CPM baseline protection, audit logging, domain outbox event emission. | Direct re-use as the sole governed path for schedule updates. |
| **Validation Service** | [`backend/app/services/validation_service.py`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/services/validation_service.py) | Validates activity updates, percent bounds, date logic, and CPM integrity. | Direct re-use before any schedule write. |
| **P6 Export** | [`backend/app/api/export.py`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/api/export.py) | Full multi-table P6 XER export (`PROJECT`, `PROJWBS`, `TASK`, `TASKPRED`). | Direct re-use. Updates made via Time Agent immediately reflect in exported XER. |
| **Frontend Workspace** | [`frontend/app/projects/[id]/page.tsx`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/frontend/app/projects/%5Bid%5D/page.tsx) | Project workspace tabs (`overview`, `wbs`, `activities`, `gantt`, `reports`). | Direct re-use. Add `Time Agent` tab / slide-over drawer. |

---

## 3. Current Extraction Pipeline

`[EXISTING]` In [`ExtractionService`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/services/extraction_service.py):
1. **Binary Retrieval**: Pulls raw bytes from MinIO using `storage_key`.
2. **Schema-Constrained LLM Call**: Invokes Gemini / OpenAI using a prompt enforcing the `NormalizedExtractionEvent` schema:
   - `verbatim_excerpt`
   - `activity_reference`
   - `reported_activity_code`
   - `description`
   - `execution_date`
   - `quantity` & `unit`
   - `location` & `discipline`
   - `contractor` & `asset`
   - `wbs_hint`
   - `status_reported`
3. **Normalization**:
   - `normalize_unit()`: Maps `cum`, `cu.m`, `cubic meter` $\rightarrow$ `m3`; `sqm` $\rightarrow$ `m2`; `tonnes` $\rightarrow$ `t`.
   - `normalize_status()`: Maps natural language terms (`complete`, `finished`, `100%`) $\rightarrow$ `COMPLETED`; (`pouring`, `started`, `ongoing`) $\rightarrow$ `IN_PROGRESS`.
4. **Extraction Confidence Formulation**:
   $$C_{\text{ext}} = 0.35 \cdot S_{\text{verbatim}} + 0.25 \cdot S_{\text{date}} + 0.20 \cdot S_{\text{fields}} + 0.20 \cdot S_{\text{ocr}}$$

---

## 4. Current Matching Pipeline

`[EXISTING]` In [`MatchingService`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/services/matching_service.py):
1. **Candidate Retrieval**:
   - Queries `activities` table filtered by active project (`project_id`) and incomplete status (`status != 'COMPLETED'`).
   - Applies temporal window: prefers activities where planned window overlaps execution date $\pm 30$ days.
2. **5-Signal Scoring Engine**:
   - $S_{\text{id}} \in \{0.0, 1.0\}$: Exact activity code match in text.
   - $S_{\text{text}} \in [0.0, 1.0]$: Token coverage (75%) + Jaccard similarity (25%) against activity name.
   - $S_{\text{wbs}} \in [0.0, 1.0]$: WBS hint and discipline alignment.
   - $S_{\text{temp}} \in [0.1, 1.0]$: Closeness of execution date to planned start/finish.
   - $S_{\text{context}} \in [0.0, 1.0]$: Physical location code ("Pier 14", "F-204") and contractor match.
3. **Weighted Total Score**:
   - If exact code present: $S_{\text{total}} = \max(0.95, 0.40 \cdot S_{\text{id}} + 0.30 \cdot S_{\text{text}} + 0.15 \cdot S_{\text{wbs}} + 0.10 \cdot S_{\text{temp}} + 0.05 \cdot S_{\text{context}})$.
   - If no code: $S_{\text{total}} = 0.45 \cdot S_{\text{text}} + 0.25 \cdot S_{\text{wbs}} + 0.15 \cdot S_{\text{temp}} + 0.15 \cdot S_{\text{context}}$.
4. **Margin Delta**:
   $$\Delta_{\text{margin}} = S_{\text{top}} - S_{\text{second}}$$
5. **Confidence Routing Rule**:
   $$S_{\text{total}} \ge 0.85 \;\wedge\; \Delta_{\text{margin}} \ge 0.15 \;\wedge\; C_{\text{ext}} \ge 0.80 \implies \mathbf{AUTO\_LINK}$$
   $$\text{Otherwise} \implies \mathbf{PLANNER\_REVIEW}$$

---

## 5. Current Schedule Update Pipeline

`[EXISTING]` In [`ScheduleUpdateService`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/services/schedule_update_service.py):
1. **Idempotency Check**:
   Queries `ActualProgressLedger` with composite unique constraint `(activity_id, execution_event_id)`. Prevents duplicate application.
2. **Progress Calculation**:
   - If quantity provided and planned quantity $>0$: $new\_pct = prev\_pct + (quantity / planned\_quantity) \cdot 100$.
   - If completed: $new\_pct = 100.0$.
   - If work reported without quantity: shifts progress by $+25\%$ up to $75\%$ max.
3. **CPM Baseline Firewall**:
   Mutates **only**: `percent_complete`, `status`, `actual_start`, `actual_finish`, `updated_at`. Planned baseline start/finish and durations are immutable.
4. **Audit & Provenance**:
   - Appends record to `ActualProgressLedger`.
   - Appends immutable audit entry to `ScheduleAuditLog` (recording user ID, artifact ID, event ID, previous state, new state).
   - Inserts event to `DomainOutbox` (`SCHEDULE_PROGRESS_UPDATED`).

---

## 6. Time Agent Purpose

`[PROPOSED]` The Time Agent serves as a conversational front-end to this entire pipeline:
1. **Accept Natural-Language Execution Reports**: Allows supervisors on-site or engineers at their desks to type or speak updates directly.
2. **Match-Aware Gap Analysis**: Detects when an execution report is ambiguous or missing key data needed to achieve $\ge 0.85$ matching confidence.
3. **Targeted Clarification Questions**: Asks the supervisor concise, specific questions to resolve ambiguity.
4. **Iterative Event Enrichment**: Integrates answers into the draft event and re-evaluates matching.
5. **Governed Execution**: Never touches the database directly; routes approved updates through `ScheduleUpdateService`.

---

## 7. Conversational Execution Reporting (Mode B)

`[PROPOSED]`
When a supervisor types:
> *"Today we completed 35 cubic meters of concrete at foundation F-204."*

The Time Agent executes the following conversational extraction:
1. **Explicit Entity Extraction**:
   - Work Description: "completed concrete"
   - Quantity: `35.0`
   - Unit: `m3` (normalized from "cubic meters")
   - Location / Asset: `F-204` / `foundation F-204`
   - Date: Current session date or explicit "today" resolved to server project date.
2. **Inferred Context**:
   - Discipline: `Civil` (inferred from "concrete foundation")
   - Status: `IN_PROGRESS` or `COMPLETED` (requires check against planned quantity)
3. **Context Injection**:
   - `project_id`: Derived strictly from active session context (cannot be guessed by LLM).
   - `user_id`: Authenticated user ID.

---

## 8. Artifact-Based Execution Reporting (Mode A)

`[PROPOSED]`
The Time Agent provides a drop zone for files within the chat interface:
1. Supervisor drops `Daily_Site_Report_Pier14.pdf` into the conversation.
2. Uploads via `POST /api/v1/projects/{id}/artifacts/upload` $\rightarrow$ MinIO $\rightarrow$ `Artifact` record.
3. Calls existing `ExtractionService.extract_artifact_events()`.
4. The Time Agent reviews the extracted events:
   - If Event 1 matches `CIV-1001` with $0.94$ score: Agent presents high-confidence confirmation.
   - If Event 2 has multiple candidates ($0.71$ vs $0.68$): Agent initiates a clarification turn citing the document.
     > *"In the uploaded report, concrete pouring on page 2 doesn't specify whether it was Pier 14 or Pier 15. Which pier was this poured for?"*

---

## 9. Unified ExecutionEvent Model

`[PROPOSED]`
To support both Mode A and Mode B seamlessly without duplicate pipelines, `ExecutionEvent` in [`backend/app/domain/models.py`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/domain/models.py) requires a minimal, non-breaking schema evolution:

```python
class ExecutionEvent(Base):
    __tablename__ = "execution_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # [MODIFIED] artifact_id becomes nullable to support pure conversational reports
    artifact_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    
    # [NEW] Track source channel
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="ARTIFACT"
    )  # 'ARTIFACT', 'CONVERSATION', 'HYBRID'

    # [NEW] Link to conversational session
    conversation_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )

    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Source provenance (populated with session details for Mode B)
    source_report_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, default=1)
    bounding_box: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Structured Execution Facts
    verbatim_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    activity_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reported_activity_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    execution_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    start_time: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    end_time: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status_reported: Mapped[str] = mapped_column(String(50), nullable=False, default="IN_PROGRESS")
    quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    discipline: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contractor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    asset: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    wbs_hint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Confidence & Matching (Reused 100% identically)
    extraction_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    extraction_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", index=True)
    # Status lifecycle: DRAFT -> UNMATCHED -> IN_REVIEW -> AUTO_LINKED -> APPLIED / REJECTED
    matched_activity_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("activities.id", ondelete="SET NULL"), nullable=True, index=True)
    match_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    match_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

---

## 10. Agent Context and Scoping

`[PROPOSED]`
The Time Agent operates under a strict, layered context model:

```text
[Global Application]
        ↓
  [Project Context: project_id (MANDATORY)]
        ↓
  [Schedule Context: schedule_version (Current Active)]
        ↓
  [Activity Context: activity_id (OPTIONAL - e.g. opened from Gantt row)]
        ↓
  [Conversation Context: conversation_id (Session Memory)]
```

### Context Rules
1. **Server-Side Project Enforcement**: The client must supply `project_id` in headers or URL path. Every activity lookup, candidate search, and schedule update is parameterized by `WHERE project_id = :project_id`.
2. **Context-Aware Prompts**: If the supervisor opens the chat while viewing activity `CIV-1001` in the Gantt chart, the client passes `activity_id: "act-civ-1001"`. The agent initializes context with that activity pre-selected:
   > *"Reporting progress for CIV-1001 (Excavation Work). Currently at 50%. What work was completed?"*
3. **No LLM Target Guessing**: The LLM is never permitted to emit an unverified activity ID or project ID.

---

## 11. Missing-Information Detection

`[PROPOSED]`
The agent analyzes the draft event against the schedule state using a deterministic verification matrix:

| Required Attribute | Why It Is Critical | Check Logic | Clarification Trigger |
|---|---|---|---|
| **Activity Identifier** | Identifies target schedule node | $S_{\text{id}} < 1.0 \wedge \Delta_{\text{margin}} < 0.15$ | When multiple candidates exist with close scores. |
| **Component / Location** | Differentiates identical tasks across units | `event.location IS NULL` while candidate activities have distinct `location_code` | Ask which foundation, pier, or bay was worked on. |
| **Quantity & Unit** | Calculates physical percent complete | `event.quantity IS NULL` on quantity-tracked activity (`planned_quantity > 0`) | Ask for physical volume, length, or count installed. |
| **Progress Semantic** | Prevents cumulative vs incremental errors | `quantity` provided but ambiguous whether shift-only or to-date | Ask: "Is this quantity for today only, or total completed to date?" |
| **Execution Date** | Determines temporal window and audit timeline | `execution_date IS NULL` | Ask when the work occurred. |

---

## 12. Clarification Question Generation

`[PROPOSED]`
The Time Agent uses a strict **Non-Redundant Question Rule**:
- Never ask for information already present in the active context.
- Never ask more than 1 or 2 targeted questions per turn.
- Frame questions with concrete candidate options whenever possible.

### Bad vs Good Clarification
- ❌ **Bad (Form-like)**:
  > *"Please state your Project ID, Activity Code, WBS, Quantity, Unit, Date, and Contractor."*
- ✅ **Good (Match-Aware & Contextual)**:
  > *"I found two matching foundation activities: **CIV-1001 (Foundation F-204)** and **CIV-1002 (Foundation F-205)**. Which foundation was the 35 m³ poured for?"*

---

## 13. Candidate-Aware Questions

`[PROPOSED]`
The Time Agent directly inspects the `score_breakdown` from [`MatchingService.evaluate_event()`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/services/matching_service.py):

```json
{
  "top_candidate": {"activity_code": "CIV-1001", "name": "Pier 14 Cap Beam", "match_score": 0.72},
  "second_candidate": {"activity_code": "CIV-1002", "name": "Pier 15 Cap Beam", "match_score": 0.69},
  "margin_delta": 0.03
}
```

The agent calculates the **differentiating feature**:
- Text difference: "Pier 14" vs "Pier 15".
- Formulates question: *"Was this pour completed for Pier 14 or Pier 15?"*

---

## 14. Re-Matching After Clarification

`[PROPOSED]`
The iterative loop proceeds as follows:

```
[Draft Event in Memory] ──► [Candidate Score: 0.72, Margin: 0.03]
                                         │
                                         ▼
                             [Agent asks: Pier 14 or 15?]
                                         │
                                         ▼
                                [User responds: "Pier 14"]
                                         │
                                         ▼
                            [Enrich event: location = "Pier 14"]
                                         │
                                         ▼
                         [Re-run MatchingService.evaluate_event()]
                                         │
                                         ▼
                        [New Score: 0.94, Margin: 0.25 -> HIGH]
```

- Maximum clarification limit: **3 turns**.
- If after 3 turns ambiguity remains: The agent routes the event to the **Planner Review Queue** (`status = "IN_REVIEW"`), notifying the user:
  > *"I've logged your report and sent it to the Planner Review queue for review, as we couldn't resolve the exact activity match."*

---

## 15. Schedule Update Flow

`[PROPOSED]`
Once confirmed, the Time Agent invokes the **existing** backend pipeline:

```python
# Invoked inside Time Agent tool executor
updated_activity = ScheduleUpdateService.apply_event_progress(
    db=db,
    event_id=event.id,
    activity_id=confirmed_activity_id,
    user_id=session.user_id,
    override_percent=confirmed_percent,
    action_name="TIME_AGENT_CONVERSATIONAL_UPDATE"
)
```

No custom SQL is written; all validation rules in `ValidationService` and audit records in `ScheduleAuditLog` and `DomainOutbox` fire automatically.

---

## 16. Confirmation Model

`[PROPOSED]`
The agent strictly separates **Intent Detection** from **Schedule Execution**:
- **Informational statements**: No confirmation needed.
- **Progress Report**: Agent constructs proposed update and presents an **Interactive Confirmation Card** in chat.

### Confirmation Card Specification
```text
┌──────────────────────────────────────────────────────────┐
│ 📋 PROPOSED SCHEDULE PROGRESS UPDATE                     │
├──────────────────────────────────────────────────────────┤
│ Activity:      CIV-1001 (Pier 14 Cap Beam Pour)         │
│ WBS:           WBS-100 (Civil)                           │
│ Current State: IN_PROGRESS (50.0%)                       │
│ Proposed State:IN_PROGRESS (75.0%)                       │
│ Incremental:   +25.0% (+35 m³ concrete)                 │
│ Execution Date:2024-09-30                                │
│ Source:        Conversational Report by VimalBisht       │
├──────────────────────────────────────────────────────────┤
│ [ ✅ Confirm & Apply Update ]      [ ✏️ Edit Details ]   │
└──────────────────────────────────────────────────────────┘
```

The update is **only** executed when the user clicks `Confirm` or says `"Yes, confirm"`.

---

## 17. Tool Layer

`[PROPOSED]`
The Time Agent uses a deterministic Function Calling / Tool Execution pattern. The LLM produces structured tool calls, which the backend executes safely against the database:

```
User Message ──► LLM Prompt with Tool Declarations ──► LLM emits ToolCall(name, args)
                                                                │
                                                                ▼
                                                    Backend Tool Executor
                                                                │
                                                                ▼
User Message ◄── LLM Summarizes Result ◄── Tool Result returned to LLM
```

---

## 18. Read Tools

`[PROPOSED]`
The backend exposes the following read tools to the Time Agent:

1. **`get_project_summary(project_id: str)`**: Returns project name, data date, planned start/finish, total activity counts.
2. **`get_activity(project_id: str, activity_code_or_id: str)`**: Returns activity details, WBS code, planned dates, current status, percent complete, planned quantity, and contractor.
3. **`search_schedule_activities(project_id: str, query: str, discipline: Optional[str] = None)`**: Performs search on activity names and codes within the project.
4. **`get_event_candidates(event_id: str)`**: Retrieves top candidate activities with score breakdown from `MatchingService`.
5. **`get_recent_audit_logs(project_id: str, limit: int = 5)`**: Retrieves recent progress updates for context.

---

## 19. Write Tools

`[PROPOSED]`
The backend exposes the following governed write tools:

1. **`create_draft_execution_event(project_id: str, payload: DraftEventCreateDTO)`**: Creates or initializes an `ExecutionEvent` in `DRAFT` status.
2. **`enrich_execution_event(event_id: str, updates: Dict[str, Any])`**: Updates fields on a draft event (location, quantity, date, etc.).
3. **`match_draft_event(event_id: str)`**: Runs `MatchingService.evaluate_event(db, event)` and returns the route (`AUTO_LINK` vs `PLANNER_REVIEW`) and candidates.
4. **`confirm_and_apply_schedule_update(event_id: str, activity_id: str, user_id: str)`**: Invokes `ScheduleUpdateService.apply_event_progress()` to execute the update.

---

## 20. MinIO Integration

`[PROPOSED]`
Chat attachments reuse the existing [`MinIOArtifactService`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/services/minio_service.py):
- Storage path: `sih-artifacts/projects/{project_id}/conversations/{conversation_id}/artifacts/{artifact_id}/{filename}`
- Cryptographic hash: SHA-256 computed prior to upload.
- Presigned URLs: Time-limited (15-minute) URLs generated via `minio_service.get_presigned_view_url()` to render document previews directly inside the chat message stream.

---

## 21. Attachment Handling

`[PROPOSED]`
1. When a user attaches a file in chat, the frontend calls `POST /api/v1/agent/conversations/{id}/attachments`.
2. The endpoint uploads to MinIO, creates an `Artifact` record, and triggers extraction via `ExtractionService`.
3. The extracted `ExecutionEvent`(s) are linked to the conversation.
4. The agent responds in the message thread:
   > *"I parsed `Shift_Log_0930.pdf` and extracted 1 execution event: **35 m³ concrete pour**. I've matched it to **CIV-1001 (Pier 14 Cap Beam)** with 94% confidence. Would you like me to record this progress?"*

---

## 22. Chat UI

`[PROPOSED]`
A modern, responsive chat component built with TailwindCSS and Lucide React:
- **Location**: Available as a dedicated **"Time Agent"** tab in [`frontend/app/projects/[id]/page.tsx`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/frontend/app/projects/%5Bid%5D/page.tsx) and as a slide-out drawer accessible from any tab (Gantt, WBS, Activities).
- **Header**: Displays active project context badge (`BOROUGE4_DEMO`) and current activity scope if launched from an activity row.
- **Message List**:
  - Supervisor speech bubbles.
  - Agent assistant bubbles with markdown formatting.
  - Interactive Action Cards (Candidate selection buttons, Confirmation Cards).
  - Presigned attachment preview links.
- **Input Area**:
  - Multi-line auto-expanding text box.
  - Attachment paperclip button (supports `.pdf`, `.xlsx`, `.csv`, `.png`, `.m4a`).
  - Send button with loading spinner.

---

## 23. Conversation State

`[PROPOSED]`
Conversation state is persisted in PostgreSQL to allow resuming sessions across browser refreshes:

```python
class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    active_activity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    active_event_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE")  # ACTIVE, RESOLVED, ABANDONED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages: Mapped[List[ConversationMessage]] = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender: Mapped[str] = mapped_column(String(50), nullable=False)  # 'USER', 'AGENT', 'SYSTEM'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON for cards / candidates
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

---

## 24. Authorization

`[PROPOSED]`
- **Field Supervisor / Engineer**: Can create conversations, report execution, answer clarification questions, and view proposed updates.
- **Lead Planner / Project Manager**: Has full authority to confirm schedule updates, override percent complete, and manage the review queue.
- If a supervisor lacks update permissions: the Time Agent creates the verified event and routes it to the **Planner Review queue**, returning:
  > *"Progress details recorded and sent to the Lead Planner for final approval."*

---

## 25. Cross-Schedule Safety

`[PROPOSED]`
**Zero Cross-Schedule Bleed**:
1. Every API call requires a path parameter `/api/v1/projects/{project_id}/agent/...`.
2. The backend validates that:
   - `conversation.project_id == project_id`
   - `activity.project_id == project_id`
   - `event.project_id == project_id`
3. Candidate retrieval in `MatchingService` queries exclusively within `Activity.project_id == project_id`. It is mathematically impossible for an event in Project A to match or mutate an activity in Project B.

---

## 26. Auditability

`[PROPOSED]`
Every conversational execution update is recorded with forensic provenance:
- **`ScheduleAuditLog`**:
  - `action`: `"TIME_AGENT_CONVERSATIONAL_UPDATE"`
  - `user_id`: Authenticated supervisor / planner
  - `execution_event_id`: UUID of the unified `ExecutionEvent`
  - `previous_state` & `new_state`: Complete JSON snapshots of progress and dates
- **`ExecutionEvent`**:
  - `verbatim_excerpt`: The supervisor's original natural-language prompt
  - `conversation_id`: Links back to the full conversational transcript
  - `match_metadata`: Stores the candidate list, match scores, and margin deltas

---

## 27. LLM Responsibilities

`[PROPOSED]`
The LLM is strictly constrained to cognitive/interpretive tasks:
- Parsing natural language into schema fields (`quantity`, `unit`, `location`, `discipline`).
- Formulating concise, friendly clarification questions based on missing fields.
- Explaining matching results in plain English.
- Formatting confirmation cards.

---

## 28. Backend Responsibilities

`[PROPOSED]`
The backend retains exclusive authority over:
- Database transactions and persistence.
- Candidate retrieval and scoring algorithms ($S_{\text{id}}, S_{\text{text}}$, etc.).
- Margin delta evaluation and confidence routing.
- CPM firewall validation (immutability of planned dates).
- Object storage and cryptographic hashing.
- Execution of schedule updates via `ScheduleUpdateService`.

---

## 29. RAG / Retrieval Strategy

`[PROPOSED]`
- **Structured Schedule State**: Retrieved directly via SQL (exact queries on `activities`, `wbs`, and `actual_progress_ledger`). Vector databases are unnecessary for schedule entities because activities have structured metadata (`activity_code`, `wbs_code`, `planned_start`).
- **Unstructured Field Reports**: When an artifact is attached, text is extracted via `pypdf`/OCR and parsed into discrete `ExecutionEvent` rows.
- **Context Injection**: The backend injects the top 5 matching candidates as JSON context into the LLM prompt, keeping prompt size tiny (< 1000 tokens) and execution fast (< 1.5s).

---

## 30. API Changes

`[NEW]` Added to [`backend/app/api/agent.py`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/api/agent.py):

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/projects/{project_id}/agent/conversations` | `POST` | Create or retrieve an active conversation session. |
| `/api/v1/projects/{project_id}/agent/conversations/{id}/messages` | `POST` | Send supervisor message; invokes agent loop; returns agent response & action cards. |
| `/api/v1/projects/{project_id}/agent/conversations/{id}/attachments` | `POST` | Upload file attachment (PDF/audio/xlsx); extracts events and integrates into conversation. |
| `/api/v1/projects/{project_id}/agent/conversations/{id}/confirm` | `POST` | Execute confirmed schedule update via `ScheduleUpdateService`. |

---

## 31. Database Changes

`[NEW]` Added to [`backend/app/domain/models.py`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/domain/models.py):
1. Create table `conversations` (id, project_id, user_id, active_activity_id, active_event_id, status, created_at, updated_at).
2. Create table `conversation_messages` (id, conversation_id, sender, content, message_metadata, created_at).
3. Alter table `execution_events`:
   - Make `artifact_id` nullable (`VARCHAR(36) NULL`).
   - Add column `source_type` (`VARCHAR(50) NOT NULL DEFAULT 'ARTIFACT'`).
   - Add column `conversation_id` (`VARCHAR(36) NULL REFERENCES conversations(id)`).

---

## 32. Frontend Changes

1. `[NEW]` [`frontend/components/TimeAgentChat.tsx`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/frontend/components/TimeAgentChat.tsx): Full-featured conversational chat component with file drop zone, message history, candidate selector, and confirmation card.
2. `[MODIFIED]` [`frontend/app/projects/[id]/page.tsx`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/frontend/app/projects/%5Bid%5D/page.tsx): Add `"time_agent"` tab and floating action button to toggle chat drawer from Gantt chart.
3. `[MODIFIED]` [`frontend/lib/api.ts`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/frontend/lib/api.ts): Add agent client functions (`startAgentConversation`, `sendAgentMessage`, `uploadAgentAttachment`, `confirmAgentScheduleUpdate`).
4. `[MODIFIED]` [`frontend/lib/types.ts`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/frontend/lib/types.ts): Add TypeScript interfaces for conversation, messages, cards, and draft events.

---

## 33. Testing Strategy

1. **Unit Tests (`test_agent_extraction.py`)**:
   - Verify parsing of explicit statements: "Poured 35 m3 concrete for F-204" $\rightarrow$ `quantity=35.0, unit="m3", location="F-204"`.
   - Verify handling of ambiguous statements: "Did concrete work today" $\rightarrow$ flags missing location and quantity.
2. **Clarification Logic Tests (`test_agent_clarification.py`)**:
   - Verify that when two candidates differ on `location`, the agent generates a question targeting location.
   - Verify event enrichment merges clarification answers into the existing draft event.
3. **Integration Tests (`test_time_agent_e2e.py`)**:
   - Complete conversational flow: Message $\rightarrow$ Draft Event $\rightarrow$ Question $\rightarrow$ Answer $\rightarrow$ Re-match $\rightarrow$ Confirmation $\rightarrow$ `ScheduleUpdateService` $\rightarrow$ DB assert `percent_complete == 75.0`.
   - Attachment flow: PDF upload in chat $\rightarrow$ MinIO upload $\rightarrow$ Extraction $\rightarrow$ Confirmation $\rightarrow$ DB assert.

---

## 34. V1 Demo Scenario

### Concrete Foundation F-204 Walkthrough

1. **Setup**: Project `BOROUGE4_DEMO`, active schedule with activities `CIV-1001` (Foundation F-204, 50% complete) and `CIV-1002` (Foundation F-205, 0% complete).
2. **Supervisor Opens Chat**:
   > **Supervisor**: *"We poured 35 cubic meters of concrete today."*
3. **Time Agent Evaluates**:
   - Extracts: `quantity=35.0`, `unit="m3"`, `discipline="Civil"`.
   - Missing: `location` / specific foundation.
   - Matching returns two candidates: `CIV-1001` (score 0.71) and `CIV-1002` (score 0.68). Margin delta = 0.03 (Ambiguous).
4. **Time Agent Clarifies**:
   > **Agent**: *"I found two concrete foundation activities in Civil: **CIV-1001 (Foundation F-204)** and **CIV-1002 (Foundation F-205)**. Which foundation was the 35 m³ placed for?"*
5. **Supervisor Clarifies**:
   > **Supervisor**: *"F-204."*
6. **Agent Enriches & Re-matches**:
   - Enriched event: `location="F-204"`.
   - Re-runs `MatchingService.evaluate_event()`.
   - Top candidate: `CIV-1001`, Match Score: **0.94**, Margin Delta: **0.25** ($\ge 0.15 \implies \mathbf{AUTO\_LINK}$).
7. **Agent Presents Confirmation Card**:
   > **Agent**: *"Matched to **CIV-1001 (Foundation F-204)** with 94% confidence. This will increase progress from 50% to 75% (+35 m³). Please confirm to update the schedule."*
   > *[Button: Confirm & Apply]*
8. **Supervisor Confirms**:
   - Supervisor clicks `[Confirm & Apply]`.
   - Calls `ScheduleUpdateService.apply_event_progress()`.
   - Progress updated in PostgreSQL: `percent_complete = 75.0%`, `status = "IN_PROGRESS"`.
   - `ActualProgressLedger` and `ScheduleAuditLog` rows created.
   - Gantt chart refreshes and displays 75% progress bar.

---

## 35. V1 Scope and Exclusions

### In-Scope for V1
- Conversational execution reporting via natural language text.
- File attachments (PDF, Excel, Audio, Images) within chat.
- Match-aware missing information detection.
- Multi-turn clarification loop (up to 3 turns).
- Interactive Confirmation Cards before schedule update.
- Complete execution through existing `ScheduleUpdateService` and audit logs.
- Real-time Gantt timeline synchronization.

### Excluded from V1 (Future Roadmap)
- Autonomous rescheduling or critical path recalculation.
- Modifying logic links (`ActivityRelationship`) or creating new activities conversationally.
- Direct database mutations outside `ScheduleUpdateService`.
- Multi-project bulk reporting in a single sentence.

---

## 36. Implementation Phases

```
Phase 1: Database & Model Layer (1 day)
  - Add conversations & conversation_messages tables
  - Make ExecutionEvent.artifact_id nullable and add source_type
  - Run database migration via init_db()

Phase 2: Conversational Extraction & Match-Aware Clarifier (2 days)
  - Implement ConversationalExtractionService
  - Implement MissingInformationDetector
  - Implement ClarificationGenerator using MatchingService score breakdowns

Phase 3: Agent Orchestrator & Tool Executor (2 days)
  - Implement TimeAgentService with read/write tool dispatcher
  - Integrate interactive confirmation card logic
  - Connect confirmed actions to ScheduleUpdateService

Phase 4: API & MinIO Integration (1.5 days)
  - Create /api/v1/projects/{id}/agent/... routes in backend/app/api/agent.py
  - Connect chat attachment handler to MinIO and ExtractionService

Phase 5: Frontend Chat Workspace (2.5 days)
  - Implement TimeAgentChat.tsx with Lucide icons, attachment handling, and action cards
  - Integrate into ProjectWorkspace tabs and add Gantt slide-over trigger
  - Connect frontend API client functions

Phase 6: Verification & Regression Suite (1 day)
  - Implement automated test suite covering Mode A, Mode B, and clarification loops
  - Verify complete round-trip through Gantt and P6 XER export
```

---

## 37. Risks and Trade-Offs

| Risk | Impact | Architectural Mitigation |
|---|---|---|
| **LLM Hallucination of Target Activity** | High (corrupts schedule) | **Strict Tool Firewall**: LLM cannot set activity IDs; only `MatchingService` scores candidates against real database records. |
| **Premature / Unintended Schedule Mutation** | High (unverified updates) | **Two-Phase Commit**: Agent only creates `DRAFT` events; schedule updates require explicit user confirmation card or button click. |
| **Chat Session Memory Bloat** | Medium (slow responses, token costs) | **Summarized Context**: Do not feed entire schedule into LLM. Inject only active project metadata, active draft event, and top 5 candidate summaries. |
| **Network / API Key Failure** | Medium (LLM unavailable) | **Graceful Degraded Fallback**: If Gemini/OpenAI API key is unavailable, agent falls back to keyword-based regex matching and routes events to Planner Review. |

---

## 38. Open Questions

1. **Voice Input on Mobile**: Should the chat interface include direct browser-based microphone recording for site supervisors using phones, feeding directly into the MinIO audio extraction pipeline? *(Recommended for V1.1)*.
2. **Batch Reporting**: If a supervisor reports three tasks in one message (*"Completed F-204 concrete, installed 20m cable tray, and finished painting"*), should V1 split this into 3 separate execution events conversationally? *(Recommended: Yes, via an events array in the conversational parser)*.
3. **Planner Review Notifications**: Should events that remain ambiguous after 3 clarification rounds trigger an in-app notification banner for the Lead Planner? *(Recommended: Yes, via standard status badge in the Reports tab)*.

---

## Final Synthesis: Answering the Core Challenge

> **"How can we add a ChatGPT-like Time Agent to ScheduleManager that allows a supervisor to report completed work directly by conversation OR attach a field report, automatically extracts the execution information, identifies the correct schedule activity, asks targeted questions whenever required information is missing, re-runs matching after the user answers, and ultimately updates the correct schedule activity through the existing governed schedule-update mechanism?"**

### The Answer
By structuring the Time Agent **not** as a separate chatbot with its own database, but as a **conversational orchestration layer** on top of ScheduleManager's proven domain services:

1. **Unified Ingestion**: Mode A (attachments) and Mode B (chat text) both emit a normalized `ExecutionEvent`.
2. **Authoritative Matching**: The draft event is passed directly to the existing [`MatchingService`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/services/matching_service.py) for candidate retrieval and 5-signal scoring.
3. **Match-Aware Intelligence**: When confidence is ambiguous, the agent examines the candidate score breakdown to ask questions targeting the exact missing feature (e.g. location or quantity type).
4. **Governed Execution**: When confidence is high or the supervisor confirms, the agent delegates to [`ScheduleUpdateService.apply_event_progress()`](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/backend/app/services/schedule_update_service.py), guaranteeing CPM baseline protection, idempotency, append-only ledger tracking, and complete audit provenance back to the conversation.
