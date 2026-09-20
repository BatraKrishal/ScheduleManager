# Field Report Extraction, Activity Matching & Governed Schedule Update
## Integration Specification for the ScheduleManager Platform

**Document Name:** `EXTRACTION_MATCHING_SCHEDULE_INTEGRATION.md`  
**Classification:** Engineering Implementation & Integration Specification  
**Baseline Codebase:** `ScheduleManager` (`c:\Users\Gues\Desktop\sihnew\ScheduleManager`)  
**Target Scheduling Systems:** Oracle Primavera P6 (Native `.xer` & XML) & Microsoft Project (XML)  
**Artifact Storage Subsystem:** MinIO S3-Compatible Object Store  
**Document Status:** Grounded Standalone Specification  

---

## Executive Summary & Foundational Rules

This document defines the complete engineering specification for building an autonomous, auditable pipeline that ingests daily construction field artifacts, stores them permanently in MinIO as immutable ground-truth evidence, extracts execution progress events, matches them to existing schedule activities, routes matches through confidence-gated planner governance, and safely updates the master project schedule.

### Strict Isolation & Grounding Rules
1. **Authoritative Codebase Grounding:** This specification is derived strictly and exclusively from the existing `ScheduleManager` codebase.
2. **Explicit Implementation Status:** 
   - **`[IMPLEMENTED IN SCHEDULEMANAGER]`**: The component, model, API, or parser currently exists in `ScheduleManager` and is directly leveraged.
   - **`[NOT IMPLEMENTED IN SCHEDULEMANAGER — PROPOSED]`**: The capability does not currently exist in `ScheduleManager` and is specified as a new standalone subsystem to be integrated.
   - **`[TO BE DECIDED]`**: Architectural alternatives requiring empirical testing or engineering discovery during implementation.
   - **`[FUTURE]`**: Advanced enterprise capabilities planned for later phases.
3. **Zero External Repository Coupling:** No code, schemas, services, or design artifacts from external repositories are referenced, imported, or assumed.

### Core Architectural Principle: Evidence is Immutable; Derived Data Can Change
A foundational rule of this architecture is the absolute separation of **source evidence** from **derived domain state**:
- **Original Field Artifacts (MinIO):** The uploaded PDF reports, contractor spreadsheets, site photos, and worker voice memos are **immutable forensic evidence**. Once stored in MinIO, they are never overwritten, modified, or discarded after extraction.
- **Derived Data (PostgreSQL & Schedule):** Extraction results, structured `ExecutionEvents`, candidate matches, confidence scores, planner decisions, and schedule updates are **derived projections**. Because the original artifact is permanently preserved in MinIO, extraction and matching models can be updated, refined, and re-executed over historical artifacts without losing original ground truth.

```
┌────────────────────────────────────────────────────────┐
│               IMMUTABLE EVIDENCE LAYER                 │
│  MinIO: Original PDF / Excel / CSV / Voice Memos       │
└──────────────────────────┬─────────────────────────────┘
                           │ Read-Only Evidence Reference
                           ▼
┌────────────────────────────────────────────────────────┐
│                DERIVED DOMAIN PROJECTIONS              │
│  Extraction Results ──► ExecutionEvents ──► Matches     │
│  ──► Planner Reviews ──► Schedule Updates ──► Ledger   │
│  (Can be reprocessed, audited, or corrected at any time)│
└────────────────────────────────────────────────────────┘
```

---

## Table of Contents
1. [System Purpose](#1-system-purpose)
2. [Input: Field Reports & Persistent MinIO Artifact Storage](#2-input-field-reports--persistent-minio-artifact-storage)
3. [Extraction Engine & Artifact Retrieval](#3-extraction-engine--artifact-retrieval)
4. [Extraction Confidence](#4-extraction-confidence)
5. [Normalization](#5-normalization)
6. [Schedule Ingestion (ScheduleManager Baseline)](#6-schedule-ingestion-schedulemanager-baseline)
7. [Primavera P6 Integration](#7-primavera-p6-integration)
8. [Microsoft Project Integration](#8-microsoft-project-integration)
9. [Schedule Representation / Canonical Model](#9-schedule-representation--canonical-model)
10. [Candidate Retrieval](#10-candidate-retrieval)
11. [Matching Engine](#11-matching-engine)
12. [Match Score](#12-match-score)
13. [Confidence Routing](#13-confidence-routing)
14. [Human Review with Direct Evidence Retrieval](#14-human-review-with-direct-evidence-retrieval)
15. [Schedule Update Engine](#15-schedule-update-engine)
16. [Progress Calculation](#16-progress-calculation)
17. [Incremental Updates](#17-incremental-updates)
18. [Artifact Hashing & Multi-Tier Idempotency](#18-artifact-hashing--multi-tier-idempotency)
19. [Validation Before Schedule Update](#19-validation-before-schedule-update)
20. [Safe Schedule Write](#20-safe-schedule-write)
21. [Transaction & Failure Handling](#21-transaction--failure-handling)
22. [Audit Trail & End-to-End Provenance](#22-audit-trail--end-to-end-provenance)
23. [Data Contracts](#23-data-contracts)
24. [API & Service Interfaces](#24-api--service-interfaces)
25. [Security & Artifact Access Control](#25-security--artifact-access-control)
26. [Performance, Optimization & Artifact Retention](#26-performance-optimization--artifact-retention)
27. [Observability](#27-observability)
28. [Complete End-to-End Examples](#28-complete-end-to-end-examples)
29. [Primavera P6 vs. Microsoft Project Differences](#29-primavera-p6-vs-microsoft-project-differences)
30. [Implementation Phases](#30-implementation-phases)
31. [Testing Strategy](#31-testing-strategy)
32. [Important Design Decisions](#32-important-design-decisions)
33. [Final End-to-End Specification Flow](#33-final-end-to-end-specification-flow)
34. [Artifact Storage Integration Summary](#34-artifact-storage-integration-summary)

---

## 1. System Purpose

### 1.1 The Operational Problem
In construction and infrastructure project management, an enormous gap exists between the **site execution plane** (unstructured daily progress reports, shift logs, subcontractor delivery tickets, worker voice memos) and the **master planning plane** (contractual Critical Path Method schedules hosted in Oracle Primavera P6 or Microsoft Project).

Today, project controls teams manually read site reports, decipher shorthand contractor descriptions, search through 10,000+ line CPM schedules to find matching activities, and manually type percent complete and actual dates into scheduling software. This manual workflow creates:
- **Severe Reporting Latency:** Progress data lags site execution by 7 to 21 days.
- **Human Transposition Errors:** Incorrect tasks are credited, distorting critical path float and earned value metrics.
- **Zero Forensic Traceability:** Project planners cannot trace why an activity was marked 60% complete or locate the original field document that authorized the date.
- **Disposable Artifact Handling:** Uploaded PDF reports are frequently discarded or stored in unindexed email threads, leaving no accessible evidence during dispute resolution or delay claim audits.

### 1.2 What Information Exists in a Field Report?
A typical field artifact contains site-level operational observations:
- Shift date and weather/site conditions.
- Work narrative: "Poured 140 m3 concrete for Pier 14 cap beam between 08:00 and 16:30".
- Contractor / Subcontractor: "Apex Civil Structures".
- Physical Location: "Bridge Pier 14, Grid C-4".
- Resource / Asset: "Pumper 02, Batch Plant 1".
- Trade / Discipline: "Concrete / Civil".
- Installed Quantities: "140 m3 of 200 m3 total".
- Work Status: "In Progress" or "Pavement Complete".
- Supporting media: Signed inspection tickets, site photos, or verbal shift handovers.

### 1.3 Why Field Reports Cannot Be Written Directly into Master Schedules
1. **Vocabulary Mismatch:** Field reports use informal trade terminology ("poured footing"), whereas schedules use structured WBS and contractual activity codes (e.g., `C-2040-FND: Substructure Concrete - Pier 14 Footing`).
2. **Granularity Discrepancy:** A single field report entry may represent half a day's work on an activity scheduled for 15 working days.
3. **Critical Path Fragility:** Master schedules are tightly coupled networks of dependencies (`FS`, `SS`, `FF`, `SF`). Directly writing arbitrary dates or percentages without validation can break network logic, cause negative float, or invalidate contract baselines.
4. **Contractual & Financial Liability:** Schedule dates drive milestone payments, delay claims, and liquidated damages. Unverified site reports must never mutate contractual baselines without auditable evidence.

### 1.4 Why Pipeline Stages Must Be Decoupled
The pipeline strictly decouples distinct operational stages:
1. **Artifact Ingestion & Storage:** Storing the raw field artifact permanently in MinIO and recording its metadata and cryptographic hash in PostgreSQL.
2. **Extracting Information:** Retrieving the artifact from MinIO and parsing text/tables/audio into structured execution events linked to the artifact ID.
3. **Matching Information:** Performing entity resolution against `ScheduleManager`'s canonical schedule to identify which planned activity corresponds to that work.
4. **Deciding Trustworthiness (Confidence Routing):** Applying mathematical scoring and ambiguity thresholds to determine whether the match proceeds automatically or requires human planner review.
5. **Updating the Schedule:** Calculating state transitions and safely dispatching validated mutations to the master schedule via governed APIs.

---

## 2. Input: Field Reports & Persistent MinIO Artifact Storage

### 2.1 Supported Field Artifact Formats `[PROPOSED]`
`ScheduleManager` currently parses schedule files (`.xer`, `.xml`, `.csv`, `.xlsx`) via `document-parser/app/parsers/`. Field artifact ingestion is **`[NOT IMPLEMENTED IN SCHEDULEMANAGER — PROPOSED]`**.

The artifact storage layer is format-agnostic and supports:
1. **Digital PDF (`.pdf`):** Formal daily site progress reports, inspection certificates, and pour cards.
2. **Scanned PDF (`.pdf`):** Handwritten supervisor shift logs, signed delivery slips, and weighbridge dockets.
3. **Spreadsheet Trackers (`.xlsx` / `.xls`):** Daily contractor quantity logs, rebar cutting lists, and concrete pour trackers.
4. **Delimited Text (`.csv`):** Automated batching plant logs and electronic turnstile access data.
5. **Worker Voice Memos / Audio Recordings (`.m4a`, `.mp3`, `.wav`):** Verbal shift logs recorded on mobile devices by site foremen.
   - **`[CURRENT STORAGE STATUS]`**: Fully stored and preserved in MinIO as immutable evidence.
   - **`[FUTURE EXTRACTION STATUS]`**: Speech-to-text transcription and verbal progress extraction is documented as a future pipeline phase; audio files are securely retained now so they can be processed once the transcription engine is activated.
6. **Supporting Image Evidence (`.jpg`, `.png`):** Photos of completed work attached to daily reports.

### 2.2 Artifact Upload & Storage Architecture
Field artifacts are never treated as transient HTTP payload streams that vanish after extraction. The original binary is permanently written to MinIO **before** extraction begins:

```
[ Worker / Site User Submits Artifact ]
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│  Artifact Upload Gateway (Backend API)                 │
│  1. Compute SHA-256 Digest across raw bytes            │
│  2. Verify Content-Type & Payload Size                 │
│  3. Assign unique artifact_id (UUIDv4)                 │
└──────────────────┬─────────────────────────────────────┘
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
┌──────────────────┐ ┌───────────────────────────────────┐
│ MinIO Object     │ │ PostgreSQL Metadata Ledger        │
│ Storage          │ │                                   │
│ Store raw binary │ │ Insert into artifacts table:      │
│ at structured    │ │ (artifact_id, project_id, sha256, │
│ object key       │ │  storage_bucket, storage_key,     │
│                  │ │  status='UPLOADED')               │
└────────┬─────────┘ └─────────────────┬─────────────────┘
         │                             │
         └──────────────┬──────────────┘
                        │ artifact_id reference
                        ▼
┌────────────────────────────────────────────────────────┐
│  Asynchronous Extraction Trigger                       │
│  (Passes artifact_id to Extraction Engine)             │
└────────────────────────────────────────────────────────┘
```

### 2.3 MinIO Object-Key Convention
Object keys in MinIO follow a deterministic, hierarchical structure organized by project and ingestion date:

```
projects/{project_id}/reports/{report_id}/artifacts/{artifact_id}/{original_filename}
```

#### Key Structure Breakdown:
- `project_id`: ID of the target project in `ScheduleManager` (e.g., `proj-90123456-7890-abcd`).
- `report_id`: UUID grouping multiple related artifacts submitted for the same daily shift (e.g., morning log + afternoon pour card).
- `artifact_id`: Immutable UUIDv4 identifying this specific file.
- `original_filename`: Sanitized original filename submitted by the user (e.g., `Daily_Site_Report_Pier14.pdf`).

#### Concrete Object Key Examples:
- **PDF Report:** `projects/proj-101/reports/rep-501/artifacts/art-8d8c9a1b/Daily_Site_Report_Pier14.pdf`
- **Voice Memo:** `projects/proj-101/reports/rep-501/artifacts/art-3f2a1b9c/foreman_shift_update_pier14.m4a`
- **Pour Spreadsheet:** `projects/proj-101/reports/rep-502/artifacts/art-7e4b2c1d/Pour_Log_2026_09_15.xlsx`

### 2.4 Conceptual Database Entity: `artifacts` Table `[PROPOSED]`
Large binary payloads are **never** stored directly in PostgreSQL. PostgreSQL maintains relational metadata and pointers to the MinIO object:

```sql
CREATE TABLE artifacts (
    id VARCHAR(36) PRIMARY KEY,                         -- artifact_id (UUIDv4)
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    report_id VARCHAR(36) NOT NULL,                     -- Logical daily submission grouping
    artifact_type VARCHAR(50) NOT NULL,                 -- 'PDF_REPORT', 'SPREADSHEET', 'VOICE_MEMO', 'IMAGE'
    original_filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    size_bytes BIGINT NOT NULL,
    sha256 VARCHAR(64) NOT NULL,                        -- Cryptographic content hash
    storage_bucket VARCHAR(100) NOT NULL DEFAULT 'sih-artifacts',
    storage_key VARCHAR(500) NOT NULL,                  -- Full MinIO S3 object key
    uploaded_by VARCHAR(100) NOT NULL DEFAULT 'site-user',
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    extraction_status VARCHAR(50) NOT NULL DEFAULT 'UPLOADED', -- 'UPLOADED', 'EXTRACTING', 'EXTRACTED', 'FAILED'
    error_message TEXT,
    
    CONSTRAINT uq_artifact_storage_key UNIQUE (storage_key)
);

CREATE INDEX ix_artifacts_project_sha ON artifacts(project_id, sha256);
CREATE INDEX ix_artifacts_report_id ON artifacts(report_id);
```

### 2.5 Conceptual Entity Hierarchy
```
Project (ScheduleManager Database)
  └── Daily Report Submission (report_id)
        └── Artifact (MinIO Binary + PostgreSQL Metadata)
              └── Extraction Job (Runs on Stored Artifact)
                    └── ExecutionEvent (Contains artifact_id reference)
```

---

## 3. Extraction Engine & Artifact Retrieval
*Status in ScheduleManager:* **`[NOT IMPLEMENTED IN SCHEDULEMANAGER — PROPOSED]`**

### 3.1 Decoupled Artifact Retrieval
The Extraction Engine does not accept raw HTTP multi-part file uploads directly into memory. Instead, it operates asynchronously on the stored MinIO artifact:
1. The extraction job is dispatched with an `artifact_id`.
2. The engine queries the PostgreSQL `artifacts` table to retrieve `storage_bucket` and `storage_key`.
3. The engine fetches the file binary stream from MinIO using the S3-compatible API.
4. If extraction fails, the binary remains safely in MinIO, and the extraction job can be retried without requesting another upload from the field worker.

### 3.2 Processing Logic
Extraction leverages a Large Language Model (LLM) constrained by a strict JSON Schema:
1. **Text & Layout Chunking:** Multi-page PDFs are parsed into text chunks with vector coordinates (`[x0, y0, x1, y1]`) and page numbers.
2. **Schema-Constrained Generation:** The LLM identifies distinct physical execution events occurring on specific calendar dates.
3. **Verbatim Ground-Truth Citation:** The extractor must quote the exact verbatim text snippet supporting each event.
4. **Provenance Attachment:** The extractor attaches `artifact_id`, `source_report_id`, `page_number`, and `bounding_box` directly to each emitted `ExecutionEvent`.

### 3.3 The Updated `ExecutionEvent` Data Model
```json
{
  "event_id": "ee-9a1b4c7d-8e2f-4a3b-9c1d-0e2f4a3b5c7d",
  "artifact_id": "art-8d8c9a1b-4f2e-4b1a-9c3d-7e2f4a3b5c7d",
  "source_report_id": "rep-7f8e9d0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a",
  "source_document_name": "Daily_Site_Report_2026_09_15_Pier14.pdf",
  "storage_key": "projects/proj-101/reports/rep-501/artifacts/art-8d8c9a1b/Daily_Site_Report_Pier14.pdf",
  "file_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "page_number": 2,
  "bounding_box": [124.5, 340.2, 512.0, 395.8],
  "verbatim_excerpt": "Completed 140 m3 concrete pouring for Pier 14 cap beam between 08:00 and 16:30. Formwork stripped and ready for curing.",
  
  "activity_reference": "Pier 14 Cap Beam",
  "reported_activity_code": null,
  "description": "Concrete pour for bridge pier cap beam",
  "execution_date": "2026-09-15",
  "start_time": "08:00",
  "end_time": "16:30",
  "status_reported": "COMPLETED",
  
  "quantity": 140.0,
  "unit": "m3",
  "location": "Pier 14",
  "discipline": "Civil / Structural",
  "contractor": "Apex Civil Structures",
  "asset": "Cap Beam Pier 14",
  "wbs_hint": "Substructure / Piers",
  
  "extraction_confidence": 0.94,
  "extraction_notes": "Explicit quantity, unit, and location identified in shift table."
}
```

---

## 4. Extraction Confidence
*Status in ScheduleManager:* **`[NOT IMPLEMENTED IN SCHEDULEMANAGER — PROPOSED]`**

### 4.1 Extraction Confidence vs. Activity Match Confidence
The system strictly decouples:
- **Extraction Confidence ($C_{\text{ext}}$):** Measures how accurately the system parsed the field artifact from MinIO (OCR fidelity, schema conformance, presence of supporting text).
- **Activity Match Confidence ($S_{\text{total}}$):** Measures how well the extracted event correlates with an existing activity in `ScheduleManager`'s schedule database.

### 4.2 Mathematical Formulation
$$C_{\text{ext}} = 0.35 \cdot S_{\text{verbatim}} + 0.25 \cdot S_{\text{date}} + 0.20 \cdot S_{\text{fields}} + 0.20 \cdot S_{\text{ocr}}$$

### 4.3 Low Extraction Confidence Routing
When $C_{\text{ext}} < 0.80$, the event routes to the Extraction Review Queue. The UI retrieves the original PDF from MinIO, highlights the page and bounding box, and allows the planner to correct or re-run extraction.

---

## 5. Normalization
*Status in ScheduleManager:* **`[NOT IMPLEMENTED IN SCHEDULEMANAGER — PROPOSED]`**

Before matching an `ExecutionEvent` against schedule activities, extracted tokens are normalized:
1. **Dates:** Converted to ISO-8601 strings (`YYYY-MM-DD`).
2. **Units:** Mapped to standard symbols (`cum`, `m^3` $\rightarrow$ `m3`; `tonnes`, `MT` $\rightarrow$ `t`).
3. **Synonyms:** Expanded (`"Pouring of conc."` $\rightarrow$ `"concrete pour"`).
4. **Contractors:** Normalized against master vendor aliases (`"Apex Civil"` $\rightarrow$ `"Apex Civil Structures"`).
5. **Status:** Mapped strictly to `ScheduleManager`'s canonical status enum (`document-parser/app/models/canonical.py`): `NOT_STARTED`, `IN_PROGRESS`, `COMPLETED`.

---

## 6. Schedule Ingestion (ScheduleManager Baseline)
*Status in ScheduleManager:* **`[IMPLEMENTED IN SCHEDULEMANAGER]`**

`ScheduleManager` already contains an authoritative schedule ingestion engine:
1. **`document-parser` (FastAPI on Port 8001):**
   - Implements `POST /parse` in `document-parser/app/main.py`.
   - File parsers: `xer_parser.py` (P6 `.xer`), `p6_xml_parser.py` (P6 XML), `csv_parser.py`, `xlsx_parser.py`.
   - Emits normalized `CanonicalSchedule` JSON (`document-parser/app/models/canonical.py`).
2. **`backend` (FastAPI on Port 8000/8080):**
   - Implements `POST /projects/import` in `backend/app/api/projects.py`.
   - `ImportService.import_schedule_file` persists schedules atomically to PostgreSQL across `projects`, `wbs`, `activities`, and `activity_relationships`.

---

## 7. Primavera P6 Integration

### 7.1 Separation of Concerns: MinIO vs. Authoritative Schedule
- **MinIO:** Stores raw field evidence (daily site logs, delivery slips, photos, audio).
- **ScheduleManager PostgreSQL:** Stores the authoritative representation of the CPM schedule imported from Primavera P6.
- **Primavera P6:** The external enterprise planning tool where baseline schedules originate.

### 7.2 Native XER Writeback Strategy `[PROPOSED]`
To write progress back to Primavera P6:
1. Retrieve original baseline `.xer` file bytes.
2. Locate the row matching `task_code = activity.activity_code` under the `%T TASK` table block.
3. Mutate only progress columns (`status_code`, `act_start_date`, `act_end_date`, `phys_complete_pct`, `remain_drtn_hr_cnt`).
4. Write the mutated `.xer` file to the staging directory and verify format integrity.

---

## 8. Microsoft Project Integration
*Status in ScheduleManager:* **`[NOT IMPLEMENTED IN SCHEDULEMANAGER — PROPOSED]`**

1. Add `document-parser/app/parsers/msp_xml_parser.py` to parse `<Project>`, `<Tasks><Task>`, and `<PredecessorLink>`.
2. Implement `MspXmlWriter` to mutate progress fields (`<PercentComplete>`, `<ActualStart>`, `<ActualFinish>`) while leaving `<Baseline>` and `<PredecessorLink>` untouched.

---

## 9. Schedule Representation / Canonical Model

`ScheduleManager` defines its canonical schedule structure via Pydantic (`document-parser/app/models/canonical.py`):
- `CanonicalProject`, `CanonicalWBSNode`, `CanonicalActivity`, `CanonicalRelationship`, `CanonicalSchedule`.

Proposed model extensions: Add optional `location_code`, `discipline`, `contractor_name`, and `planned_quantity` to `CanonicalActivity` and the PostgreSQL `activities` table to empower high-confidence candidate matching.

---

## 10. Candidate Retrieval
*Status in ScheduleManager:* **`[NOT IMPLEMENTED IN SCHEDULEMANAGER — PROPOSED]`**

Candidate activities are retrieved via fast SQL queries targeting `ScheduleManager`'s `activities` table:
- Filtered by `project_id`.
- Temporal window: `planned_start <= event_date + 30d` AND `planned_finish >= event_date - 30d`.
- Active status: `status != 'COMPLETED'`.
- Narrows the search pool from 50,000 to $< 25$ candidate activities.

---

## 11. Matching Engine
*Status in ScheduleManager:* **`[NOT IMPLEMENTED IN SCHEDULEMANAGER — PROPOSED]`**

The Matching Engine compares the `ExecutionEvent` against retrieved candidate activities using:
1. **Deterministic Exact Code Signal ($S_{\text{id}} \in \{0.0, 1.0\}$)**
2. **Text & Token Similarity ($S_{\text{text}} \in [0.0, 1.0]$)**
3. **WBS & Hierarchy Alignment ($S_{\text{wbs}} \in [0.0, 1.0]$)**
4. **Temporal Compatibility ($S_{\text{temp}} \in [0.0, 1.0]$)**
5. **Contextual Alignment ($S_{\text{context}} \in [0.0, 1.0]$)**

---

## 12. Match Score
$$S_{\text{total}} = w_{\text{id}} \cdot S_{\text{id}} + w_{\text{text}} \cdot S_{\text{text}} + w_{\text{wbs}} \cdot S_{\text{wbs}} + w_{\text{temp}} \cdot S_{\text{temp}} + w_{\text{context}} \cdot S_{\text{context}}$$
$$\Delta_{\text{margin}} = S_{\text{top}} - S_{\text{second}}$$

---

## 13. Confidence Routing

```
                     [ Final Match Score S_total ]
                                  │
                                  ▼
      Is S_total >= 0.85 AND Margin Delta >= 0.15 AND C_ext >= 0.80 ?
                        /                  \
                      YES                   NO
                       │                     │
                       ▼                     ▼
             [ AUTO-LINK ROUTE ]     [ HUMAN REVIEW ROUTE ]
             ├── Log Confidence      ├── Queue in Planner Dashboard
             ├── Generate Update     ├── Provide MinIO Evidence Link
             └── Execute Outbox      └── Require Explicit Sign-Off
```

---

## 14. Human Review with Direct Evidence Retrieval
*Status in ScheduleManager:* **`[NOT IMPLEMENTED IN SCHEDULEMANAGER — PROPOSED]`**

When an event routes to Planner Review ($S_{\text{total}} < 0.85$ or $\Delta_{\text{margin}} < 0.15$), the planner must not be expected to guess based on an isolated text snippet.

### 14.1 Direct MinIO Evidence Integration
The frontend Planner Review interface incorporates direct evidence access:
1. **Presigned Evidence URL:** The backend generates a temporary, signed MinIO download/view URL (`GET /api/v1/artifacts/{artifact_id}/view-url`).
2. **Left Panel — Evidence Viewer:**
   - **For PDFs:** The browser renders the original PDF with page number and vector bounding box highlighted.
   - **For Voice Memos:** An embedded audio player allows the planner to listen to the foreman's voice recording alongside any preliminary transcripts.
   - **For Spreadsheets:** Displays original sheet, row, and column context.
3. **Right Panel — Candidate Comparison:** Displays top matching activities, score breakdowns, and CPM predecessor/successor networks.
4. **Planner Sign-Off:** The planner approves, reassigns, or rejects the match. The approval record links the planner's user ID directly to the `artifact_id`.

---

## 15. Schedule Update Engine
*Status in ScheduleManager:* **`[PARTIALLY IMPLEMENTED IN SCHEDULEMANAGER]`**

Approved events trigger `ScheduleUpdateCommand` objects that invoke `ScheduleManager`'s existing API:
- `PATCH /activities/{activity_id}` in `backend/app/api/activities.py`.
- Accepts `ActivityUpdate` schema (`backend/app/schemas/activity.py`).
- Validates changes via `ValidationService.validate_activity_update`.

---

## 16. Progress Calculation
*Status in ScheduleManager:* **`[NOT IMPLEMENTED IN SCHEDULEMANAGER — PROPOSED]`**

Handles the 4 execution states (`NOT_STARTED`, `IN_PROGRESS`, `COMPLETED`). Physical percent complete is calculated from explicit reported percentage, installed quantity ratios, or certified shift completion narratives.

---

## 17. Incremental Updates
*Status in ScheduleManager:* **`[NOT IMPLEMENTED IN SCHEDULEMANAGER — PROPOSED]`**

Progress is tracked via an append-only `actual_progress_ledger` table in PostgreSQL. Each entry references `activity_id` and `execution_event_id`, ensuring cumulative physical progress is derived mathematically and preventing regression or double counting.

---

## 18. Artifact Hashing & Multi-Tier Idempotency

### 18.1 Content Hash (`sha256`) vs. Instance Identity (`artifact_id`)
To maintain complete integrity, the system distinguishes between content fingerprinting and instance identity:
- **`artifact_id` (UUIDv4):** Identifies a specific upload transaction.
- **`sha256` (Content Hash):** Hex-encoded SHA-256 digest calculated across the raw file bytes upon receipt.

### 18.2 Content Deduplication Workflow
```
[ Incoming Artifact Upload ]
             │
             ▼
[ Compute SHA-256 Hash ]
             │
             ▼
[ Query artifacts table: project_id + sha256 ]
             │
      Does record exist?
       /              \
     YES               NO
      │                 │
      ▼                 ▼
[ Check Extraction   [ Write file to MinIO ]
  Status ]           [ Insert artifacts record ]
      │              [ Trigger Extraction ]
   EXTRACTED?
    /       \
  YES        NO
   │          │
   ▼          ▼
[ Return     [ Re-queue extraction ]
  Cached     [ for existing artifact ]
  Events ]
```

### 18.3 Business Idempotency
A content hash prevents duplicate storage and redundant LLM extraction calls. However, full business idempotency also validates:
- `UNIQUE(activity_id, execution_event_id)` on `actual_progress_ledger`.
- `UNIQUE(source_report_id, page_number, verbatim_excerpt_hash)` on `execution_events`.
- Idempotency key on `ScheduleUpdateCommand`: `hash(activity_id + event_id + execution_date)`.

---

## 19. Validation Before Schedule Update

A 13-point validation checklist verifies project existence, activity existence, status validity, percent complete bounds ($[0, 100]$), date chronological integrity, and strictly enforces the **CPM Schedule Firewall** (forbidding alterations to baseline dates or logic links).

---

## 20. Safe Schedule Write

Updates commit to PostgreSQL (`PATCH /activities/{id}`), immediately updating Gantt and Spreadsheet views. Simultaneously, an outbox task is inserted into `domain_outbox` `[PROPOSED NEW TABLE]`. Asynchronous worker daemons poll the outbox (`SKIP LOCKED`) and dispatch mutations to external Primavera P6 `.xer` or MS Project `.xml` files.

---

## 21. Transaction & Failure Handling

### 21.1 Extraction Failure & Artifact Resilience
A primary benefit of MinIO storage is that **extraction failures never cause data loss**.

If an LLM times out, hits rate limits, or produces unparseable JSON:
1. The original artifact remains safely stored in MinIO.
2. The `artifacts.extraction_status` is updated to `'FAILED'` with the error message recorded.
3. The system retries extraction automatically with exponential backoff.
4. The field worker does **not** need to re-upload the document.

### 21.2 Failure Handling Matrix
| Failure Scenario | Impact | System Response & Mitigation |
| :--- | :--- | :--- |
| **MinIO Unavailable During Upload** | Artifact cannot be stored | Upload fails safely (`HTTP 503`); transaction aborted; no partial database records created; client prompted to retry. |
| **Artifact Stored, but Extraction Fails** | Execution events not created | Artifact binary preserved in MinIO; status set to `FAILED`; extraction job retried asynchronously. |
| **Duplicate Artifact Uploaded** | Redundant file submitted | Detected via SHA-256; upload acknowledged; duplicate extraction avoided by reusing cached execution events. |
| **Matching Fails (Zero Candidates)** | Event unlinked | Event marked `UNMATCHED`; original MinIO artifact remains accessible for manual planner assignment. |
| **Planner Rejects Match** | Proposed activity dismissed | Rejection audit event recorded; original MinIO evidence remains linked to the rejected event for audit inspection. |
| **Schedule Update Fails (DB Lock)** | Master schedule not mutated | Outbox worker rolls back transaction; retries with exponential backoff; artifact and execution events remain intact. |
| **MinIO Temporarily Unavailable During Review** | PDF/Audio preview fails to load | Domain state in PostgreSQL remains intact; frontend shows graceful retry alert; review queue operations resume once MinIO recovers. |

---

## 22. Audit Trail & End-to-End Provenance

### 22.1 Complete Traceability Chain
Every schedule update maintains an unbroken forensic chain back to the original binary artifact:

```
SCHEDULE MUTATION (Activity CIV-2040: 70% Complete)
        │
        ▼ (authorized by)
APPROVED PROGRESS LEDGER (actual_progress_ledger.id)
        │
        ▼ (derived from)
EXECUTION EVENT (event_id, verbatim_excerpt, page_number)
        │
        ▼ (extracted from)
EXTRACTION RESULT (job_id, extraction_confidence = 0.94)
        │
        ▼ (originating from)
ARTIFACT METADATA (artifact_id, sha256, storage_key)
        │
        ▼ (stored permanently in)
MINIO OBJECT (sih-artifacts/projects/.../Daily_Site_Report.pdf)
```

### 22.2 Why Preserving Original Evidence Matters
1. **Forensic Audit & Delay Claims:** Contractual disputes and claims for time extension require original contemporaneous evidence, not just derived database rows.
2. **Planner Review Grounding:** Planners can visually verify extracted quantities against original site paperwork.
3. **Model Improvement & Backtesting:** When extraction prompts or matching algorithms improve, historical artifacts can be re-extracted and re-evaluated against past performance.
4. **Error Investigation:** If an incorrect activity was credited, project controls can inspect the source document to verify whether the error occurred during field reporting, LLM extraction, or matching.

---

## 23. Data Contracts

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ArtifactDTO(BaseModel):
    artifact_id: str
    project_id: str
    report_id: str
    artifact_type: str # "PDF_REPORT", "SPREADSHEET", "VOICE_MEMO", "IMAGE"
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    storage_bucket: str
    storage_key: str
    uploaded_by: str
    uploaded_at: datetime
    extraction_status: str

class ExecutionEventDTO(BaseModel):
    event_id: str
    artifact_id: str
    source_report_id: str
    source_filename: str
    storage_key: str
    page_number: int
    bounding_box: Optional[List[float]] = None
    verbatim_excerpt: str
    description: str
    execution_date: str
    status_reported: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    location: Optional[str] = None
    discipline: Optional[str] = None
    contractor: Optional[str] = None
    extraction_confidence: float

class MatchCandidateDTO(BaseModel):
    activity_id: str
    activity_code: str
    activity_name: str
    wbs_code: Optional[str] = None
    match_score: float
    margin_delta: float
    score_breakdown: dict

class ConfidenceRoutingResultDTO(BaseModel):
    event_id: str
    artifact_id: str
    route: str # "AUTO_LINK", "PLANNER_REVIEW", "UNMATCHED"
    selected_candidate: Optional[MatchCandidateDTO] = None
    all_candidates: List[MatchCandidateDTO] = []
```

---

## 24. API & Service Interfaces

### 24.1 Existing APIs in ScheduleManager
- `GET /projects`: List all projects (`backend/app/api/projects.py`).
- `POST /projects/import`: Upload schedule file (`backend/app/api/projects.py`).
- `GET /projects/{id}/activities`: Paginated, filtered activities (`backend/app/api/activities.py`).
- `PATCH /activities/{id}`: Update schedule data (`backend/app/api/activities.py`).
- `POST /parse`: Normalize schedule files to canonical JSON (`document-parser/app/main.py`).

### 24.2 Proposed New APIs for Field Artifact & Integration Pipeline
```
POST /api/v1/projects/{project_id}/artifacts/upload
├── Multipart form upload (PDF, Excel, CSV, Audio)
├── Writes binary to MinIO & inserts metadata to PostgreSQL
└── Returns ArtifactDTO with artifact_id and sha256

GET /api/v1/artifacts/{artifact_id}
├── Retrieves artifact metadata record from PostgreSQL
└── Returns ArtifactDTO

GET /api/v1/artifacts/{artifact_id}/view-url
├── Generates time-limited presigned MinIO GET URL (e.g., 15-minute expiry)
└── Returns {"url": "https://minio.../projects/...?token=..."}

POST /api/v1/artifacts/{artifact_id}/extract
├── Triggers extraction engine to retrieve MinIO binary and parse events
└── Returns List[ExecutionEventDTO]

POST /api/v1/matching/evaluate
├── Evaluates ExecutionEvents against ScheduleManager activities
└── Returns ConfidenceRoutingResultDTO

POST /api/v1/review/decisions
├── Submits planner approval, reassignment, or rejection
└── Dispatches ScheduleUpdateCommand to backend PATCH /activities/{id}

GET /api/v1/review/queue?project_id={id}
└── Lists pending ambiguous events requiring planner review with artifact_ids
```

---

## 25. Security & Artifact Access Control

1. **Private MinIO Storage:** MinIO buckets are private. No public or anonymous read access is permitted.
2. **Credential Isolation:** The frontend browser never receives `MINIO_ACCESS_KEY` or `MINIO_SECRET_KEY`.
3. **Presigned URL Brokerage:** The backend acts as the authorization broker. When an authenticated user requests to view evidence, the backend validates project access permissions and generates a temporary presigned URL (15-minute lifetime).
4. **Project Authorization Boundary:** A user can only access artifacts belonging to projects they are explicitly authorized to view in `ScheduleManager`.
5. **Encryption:** Artifacts are encrypted at rest using MinIO SSE-S3 / SSE-KMS (AES-256) and in transit over TLS 1.3.

---

## 26. Performance, Optimization & Artifact Retention

1. **Streaming Uploads:** The backend streams artifact bytes directly to MinIO, avoiding loading multi-megabyte files entirely into application heap memory.
2. **Retention Policies:**
   - **Original Field Artifacts:** Retained permanently for the lifespan of the construction contract plus statutory warranty periods (e.g., 5 to 10 years).
   - **Temporary Extraction Intermediates:** OCR text dumps and temporary image tiles configured with shorter retention rules (e.g., 30 to 90 days).
3. **Candidate Pruning:** SQL pre-filtering ensures matching only evaluates active tasks within $\pm 30\text{ days}$ of execution dates.

---

## 27. Observability

1. **Prometheus Metrics:**
   - `artifact_uploads_total`: Count of uploads by MIME type and project.
   - `artifact_storage_bytes`: Gauge of total storage consumed in MinIO.
   - `minio_request_duration_seconds`: Histogram of MinIO read/write latencies.
   - `extraction_failures_total`: Counter of failed extraction jobs.
2. **OpenTelemetry Distributed Tracing:** Trace spans connecting Artifact Upload $\rightarrow$ MinIO PutObject $\rightarrow$ Database Insert $\rightarrow$ LLM Extraction $\rightarrow$ Activity Match $\rightarrow$ Schedule Mutation.

---

## 28. Complete End-to-End Examples

### 28.1 Example 1: High-Confidence Concrete Pour with PDF Stored in MinIO
1. **Upload:** Site engineer submits `Daily_Site_Report_Pier14.pdf`.
   - Backend streams file to MinIO: `projects/proj-101/reports/rep-501/artifacts/art-8d8c9a1b/Daily_Site_Report_Pier14.pdf`.
   - Records metadata in `artifacts` table (`sha256 = e3b0c...`).
2. **Extraction:** Worker fetches binary from MinIO, parses text on page 2.
   - Emits `ExecutionEvent` (`quantity = 140 m3`, `Pier 14 Cap Beam`, `artifact_id = art-8d8c9a1b`, $C_{\text{ext}} = 0.94$).
3. **Matching:** Scored against `activities` table. Top candidate `CIV-2040: Pier 14 Cap Beam Concrete` scores $S_{\text{total}} = 0.92$ with margin $\Delta = 0.30$.
4. **Confidence Routing:** Routes to **AUTO-LINK**.
5. **Schedule Update:** Dispatches `PATCH /activities/{id}` setting `percent_complete = 70.0`.
6. **Audit Verification:** Audit entry references `artifact_id`, enabling one-click retrieval of the original PDF from MinIO.

### 28.2 Example 2: Ambiguous Match with Voice Memo Grounding
1. **Upload:** Foreman uploads voice recording `shift_summary_west_wing.m4a`.
   - Stored in MinIO: `projects/proj-101/reports/rep-502/artifacts/art-3f2a1b9c/shift_summary_west_wing.m4a`.
   - Metadata recorded with `artifact_type = 'VOICE_MEMO'`.
2. **Matching:** Text log notes installation of 45m ductwork on Level 2.
   - Candidate 1: `MEP-301: Level 2 East Wing` ($S = 0.74$).
   - Candidate 2: `MEP-302: Level 2 West Wing` ($S = 0.73$). Margin $\Delta = 0.01$.
3. **Confidence Routing:** Routes to **PLANNER REVIEW QUEUE**.
4. **Planner Verification:** Planner opens review workspace. The UI generates a presigned URL for `shift_summary_west_wing.m4a`. The planner listens to the foreman's voice recording stating work was completed in the West Wing.
5. **Approval:** Planner confirms `MEP-302`. Activity updated with planner signature and linked to `artifact_id`.

---

## 29. Primavera P6 vs. Microsoft Project Differences

| Concern | Oracle Primavera P6 | Microsoft Project |
| :--- | :--- | :--- |
| **Native Storage Model** | Relational Database (Oracle / SQL Server) | Desktop Binary (`.mpp`) or XML file |
| **Exchange File Format** | Proprietary `.xer` (tab-delimited) & P6 XML | MS Project XML (`xmlns="http://schemas.microsoft.com/project"`) |
| **Activity Identifier** | `TASK.task_code` (e.g., `A1010`) & `task_id` | `<Task><UID>` & `<Task><ID>` |
| **WBS Representation** | Explicit `PROJWBS` relational table | Hierarchical Outline Level / WBS string |
| **Percent Complete Types** | Physical %, Duration %, Units % | Single `% Complete` & `% Work Complete` |
| **Source Evidence Role** | **Stored in MinIO; P6 receives progress values** | **Stored in MinIO; MSP receives progress values** |
| **ScheduleManager Status** | **Implemented (`xer_parser.py`, `p6_xml_parser.py`)** | **`[NOT IMPLEMENTED — PROPOSED]`** |

---

## 30. Implementation Phases

```
Phase 1: Extend Canonical Models & Database Schema (Add discipline, location, contractor)
   │
   ▼
Phase 2: Deploy MinIO Infrastructure & Implement Artifact Storage Gateway
   │     - MinIO container with persistent Docker volume minio_data
   │     - artifacts table in PostgreSQL & S3 streaming client
   ▼
Phase 3: Implement LLM Extraction Engine with MinIO Retrieval & Verbatim Proofing
   │
   ▼
Phase 4: Build Normalization Engine (Dates, units, synonyms)
   │
   ▼
Phase 5: Implement SQL Candidate Retrieval & Multi-Signal Matching Engine
   │
   ▼
Phase 6: Build Confidence Router & Ambiguity Margin Evaluator
   │
   ▼
Phase 7: Develop Next.js Planner Review Queue with Presigned Evidence Viewing
   │
   ▼
Phase 8: Implement Append-Only ActualProgress Ledger & State Derivation Service
   │
   ▼
Phase 9: Implement Pre-Update Validation Firewall & Outbox Worker
   │
   ▼
Phase 10: Implement Outbound Primavera P6 XER Writer & MS Project XML Adapter
   │
   ▼
Phase 11: End-to-End Verification, Performance Benchmarking & Hardening
```

---

## 31. Testing Strategy

1. **Artifact Ingestion & Storage Tests:**
   - Verify upload streams binary to MinIO and inserts metadata to PostgreSQL.
   - Verify duplicate upload of identical file returns cached record via SHA-256.
2. **MinIO Persistence Verification:**
   - Verify artifacts persist and remain retrievable across MinIO container restarts.
3. **Extraction Provenance Tests:**
   - Verify emitted `ExecutionEvent` contains correct `artifact_id` and coordinates.
4. **Presigned URL Authorization Tests:**
   - Verify unauthorized users receive `401/403` when requesting presigned artifact URLs.
5. **Round-Trip Master Schedule Verification:**
   - Verify mutations write to P6 `.xer` without altering baseline dates or CPM links.

---

## 32. Important Design Decisions

| Decision Area | Proposed Architecture | Engineering Justification | Status in Platform |
| :--- | :--- | :--- | :--- |
| **Artifact Storage** | MinIO S3-Compatible Object Store | Eliminates database bloat; preserves original raw files as immutable forensic evidence. | `[PROPOSED]` |
| **Schedule Authority** | Relational PostgreSQL in `ScheduleManager` | Acts as canonical hub isolating master CPM schedule from site noise. | `[IMPLEMENTED]` |
| **Schedule Parsing** | `document-parser` FastAPI Microservice | Isolates CPU-heavy file parsing from web transactions. | `[IMPLEMENTED]` |
| **Field Report Extraction** | LLM with Strict JSON Schema & Verbatim Grounding | Handles highly variable site log formatting while enforcing structured types. | `[PROPOSED]` |
| **Voice Memos** | Format-Agnostic Storage in MinIO | Preserves audio recordings as evidence now; enables future transcription engines. | `[PROPOSED STORAGE / FUTURE EXTRACTION]` |
| **Progress Accounting** | Append-Only Event Sourcing Ledger | Prevents regression, double-counting, and out-of-order date anomalies. | `[PROPOSED]` |
| **Writeback Strategy** | Native File Mutation (`.xer` / `.xml`) | Enables zero-footprint operation in air-gapped field offices without enterprise servers. | `[PROPOSED]` |

---

## 33. Final End-to-End Specification Flow

```
                 FIELD REPORT / VOICE MEMO / SPREADSHEET
                                │
                                ▼ (1)
                       DOCUMENT INGESTION
                    (SHA-256 Checksum & Validation)
                                │
                                ▼ (2)
                     MINIO ARTIFACT STORAGE
               (Store Binary at projects/.../original.pdf)
                                │
                                ▼ (3)
                    POSTGRESQL METADATA RECORD
               (Insert artifacts: artifact_id, sha256)
                                │
                                ▼ (4)
                        EXTRACTION ENGINE
               (Fetches Binary from MinIO via S3 API)
                                │
                                ▼ (5)
                     STRUCTURED EXECUTION EVENT
               (Retains artifact_id & Verbatim Excerpt)
                                │
                                ▼ (6)
                        NORMALIZATION LAYER
                  (Dates, Units, Disciplines, Assets)
                                │
                                ▼ (7)
                       CANDIDATE RETRIEVAL
             [Targeting ScheduleManager activities table]
              (Active Status, Temporal Window ±30d, Disc)
                                │
                                ▼ (8)
                     MULTI-FEATURE MATCHING
                  (S_total = Σ w_i * S_i, Margin Δ)
                                │
                                ▼ (9)
                       CONFIDENCE ROUTING
                           /          \
                    (Score >= 0.85     (Score < 0.85
                    & Margin >= 0.15)   or Margin < 0.15)
                          /              \
                         ▼                ▼
                   AUTO-LINK ROUTE    PLANNER REVIEW QUEUE
                         │           (Fetches MinIO Presigned URL)
                         │ (Auto-Approved)│ (Planner Inspects Evidence)
                         └───────┬────────┘
                                 ▼ (10)
                         APPROVED MATCH EVENT
                                 │
                                 ▼ (11)
                      ACTUAL PROGRESS LEDGER
                   (Append-Only Event Sourcing)
                                 │
                                 ▼ (12)
                      STATE DERIVATION SERVICE
              (Status, Physical % Complete, Remaining Dur)
                                 │
                                 ▼ (13)
                      SCHEDULE UPDATE COMMAND
                    (Decoupled Mutation Envelope)
                                 │
                                 ▼ (14)
                    13-POINT VALIDATION CHECKLIST
               [Leveraging ValidationService in Backend]
                 (Firewall: Zero Protected Fields)
                                 │
                                 ▼ (15)
                      TRANSACTIONAL OUTBOX
                (PostgreSQL SKIP LOCKED Polling Worker)
                                 │
                                 ▼ (16)
                    OUTBOUND SCHEDULE ADAPTERS
                    ┌────────────┴────────────┐
                    ▼                         ▼
              PRIMAVERA P6              MS PROJECT
              (XER Writer:              (XML Writer:
              Mutate %T TASK)           Mutate <Task>)
                    │                         │
                    └────────────┬────────────┘
                                 ▼ (17)
                      VERIFY WRITTEN ARTIFACT
            [Re-parse via ScheduleManager document-parser]
               (Confirm Zero Baseline Drift via Re-parse)
                                 │
                                 ▼ (18)
                     CRYPTOGRAPHIC AUDIT TRAIL
             (Full Lineage: P6 Activity ◄──► ExecutionEvent
                         ◄──► Artifact ◄──► MinIO Binary)
```

---

## 34. Artifact Storage Integration Summary

### 1. What is Stored in MinIO
MinIO serves as the dedicated, persistent, S3-compatible object store for all raw, unedited field artifacts submitted from construction sites. This includes vector PDFs, scanned paper inspection forms, contractor Excel pour trackers, automated CSV sensor logs, site photos, and foreman voice recordings. Raw binaries are stored under structured, deterministic object keys (`projects/{project_id}/reports/{report_id}/artifacts/{artifact_id}/{original_filename}`) backed by persistent storage volumes (`minio_data`).

### 2. What is Stored in PostgreSQL
PostgreSQL strictly stores structured relational domain entities, application state, and metadata. Large binary files are never stored in the database. PostgreSQL stores:
- Artifact metadata records (`id`, `project_id`, `report_id`, `sha256`, `mime_type`, `size_bytes`, `storage_bucket`, `storage_key`, `extraction_status`).
- Canonical project planning entities (`projects`, `wbs`, `activities`, `activity_relationships`).
- Extracted `ExecutionEvents` and `ActualProgress` ledger entries.
- Transactional outbox tasks and immutable audit logs.

### 3. How Extraction Accesses Artifacts
The Extraction Engine is decoupled from file upload HTTP requests. When an artifact is uploaded, it is written to MinIO first, and an asynchronous extraction task is created with the `artifact_id`. The extraction engine queries PostgreSQL for the `storage_key`, fetches the binary stream from MinIO via S3 API calls, chunks the document, and executes schema-constrained LLM parsing. If extraction fails, the artifact remains intact in MinIO for automated retry without user re-upload.

### 4. How Execution Events Retain Provenance
Every `ExecutionEvent` emitted by the extraction engine contains an explicit foreign key reference to `artifact_id`, the source `storage_key`, the `file_sha256` content hash, the document `page_number`, the vector `bounding_box`, and the exact `verbatim_excerpt` from the source document that proves the work occurred.

### 5. How Matching and Review Use Provenance
The matching engine evaluates `ExecutionEvents` against candidate activities retrieved from `ScheduleManager`'s database. When a match is ambiguous ($S_{\text{total}} < 0.85$ or $\Delta_{\text{margin}} < 0.15$), the event is placed in the Planner Review Queue. The frontend review workspace uses the event's `artifact_id` to request a short-lived presigned URL from the backend, rendering the original PDF with highlighted coordinates or loading the foreman's audio recording directly in the planner's browser.

### 6. How Schedule Updates Remain Traceable
When an update is approved (autonomously or via planner sign-off), the system creates an immutable audit record linking the mutated schedule activity (e.g., `CIV-2040`) to the `actual_progress_ledger` ID, which traces back to the `event_id`, the `extraction_id`, the `artifact_id`, and ultimately the physical binary object in MinIO. Any project auditor can answer *"Why was this task updated?"* and immediately retrieve the original signed field report that authorized the change.

### 7. How the Design Supports Future Voice Artifacts
The storage architecture is format-agnostic. Voice recordings (`.m4a`, `.mp3`, `.wav`) are accepted at the artifact upload gateway, assigned an `artifact_id`, and stored permanently in MinIO under the same project/report hierarchy. While audio transcription and verbal progress extraction are documented as future extensions, voice memos are securely retained today as auditable evidence that planners can listen to during manual reviews.

### 8. Why Preserving the Original Artifact is Important
In construction project controls, **evidence is immutable, while derived data can change**. Field reports are legal and contractual records that substantiate progress claims, milestone billing, and delay dispute defenses. Treating original artifacts as disposable temporary input destroys forensic traceability. By preserving original artifacts in MinIO, `ScheduleManager` guarantees complete audit compliance and retains the ability to re-extract and re-match historical records as AI extraction and CPM planning models evolve.
