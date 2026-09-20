# ScheduleManager

**AI-Assisted Primavera P6 Schedule Management Platform**  
*Bridging Planned Schedules with Real-World Field Execution Through Governed Activity Matching, Conversational Time Agent Interactions, Transactionally Audited Schedule Mutations, and Structured Institutional Memory.*

---

```
                 ScheduleManager Platform

      PLAN                                 EXECUTE
       │                                      │
       │                              Field Evidence
       │                        (Daily Reports, Spreadsheets,
Primavera P6 XER / XML          Conversations, Audio Memos)
       │                                      │
       └───────────────┐      ┌───────────────┘
                       ↓      ↓
                 ExecutionEvent
                       ↓
         Multi-Signal Matching Engine
                       ↓
             Confidence Governance
            ┌──────────┴──────────┐
            ↓                     ↓
       [AUTO_LINK]         [PLANNER_REVIEW]
      (Score ≥ 0.85)       (Ambiguity / Margin < 0.15)
            │                     │
            │           ┌─────────┴─────────┐
            │           ↓                   ↓
            │      Time Agent         Lead Planner
            │     Clarification       Review Queue
            │           │                   │
            └───────────┼───────────────────┘
                        ↓
                 UpdateProposal
                        ↓
             Explicit Human Confirmation
                        ↓
             ScheduleUpdateService
            (Row Locks + CPM Invariant Firewall)
            ┌───────────┴───────────┐
            ↓                       ↓
      Current Schedule      ActualProgressLedger
      (Activities Table,     (Append-Only Execution History)
       Gantt, XER Export)           ↓
                            ScheduleAuditLog
                             (Full Lineage to Artifact / MinIO)
                                    ↓
                        Institutional Memory V1
                       (Deterministic Analytics Engine)
                                    ↓
                       ┌────────────┴────────────┐
                       ↓                         ↓
             Observed Productivity       Duration Variances
             & Planning Benchmarks       & Historical Query
```

---

## Table of Contents

1. [Problem Statement (SIH26122)](#1-problem-statement-sih26122)
2. [High-Level Solution](#2-high-level-solution)
3. [System Architecture](#3-system-architecture)
4. [Distinction of Core Concepts & Memory Types](#4-distinction-of-core-concepts--memory-types)
5. [Authoritative Data Model](#5-authoritative-data-model)
6. [Schedule Ingestion & P6 Interoperability](#6-schedule-ingestion--p6-interoperability)
7. [Field Ingestion & Execution Event Model](#7-field-ingestion--execution-event-model)
8. [Deterministic Multi-Signal Matching Engine](#8-deterministic-multi-signal-matching-engine)
9. [Time Agent](#9-time-agent)
10. [Governed Bulk Intent](#10-governed-bulk-intent)
11. [Progress Semantics & Schedule Update Governance](#11-progress-semantics--schedule-update-governance)
12. [Actual Progress Ledger & Audit Trail](#12-actual-progress-ledger--audit-trail)
13. [Institutional Memory Engine V1](#13-institutional-memory-engine-v1)
14. [Frontend Workspace Structure](#14-frontend-workspace-structure)
15. [Verified API Reference](#15-verified-api-reference)
16. [Technology Stack](#16-technology-stack)
17. [Docker & Local Development Setup](#17-docker--local-development-setup)
18. [Environment Variables](#18-environment-variables)
19. [Automated Test Suite](#19-automated-test-suite)
20. [End-to-End Demo Walkthrough](#20-end-to-end-demo-walkthrough)
21. [Current Feature Matrix](#21-current-feature-matrix)
22. [V1 Limitations & Engineering Non-Claims](#22-v1-limitations--engineering-non-claims)
23. [Product Roadmap](#23-product-roadmap)
24. [Repository Structure](#24-repository-structure)
25. [Engineering Grounding & Invariant Commitments](#25-engineering-grounding--invariant-commitments)

---

## 1. Problem Statement (SIH26122)

In large-scale capital infrastructure and construction projects, a systemic disconnect exists between engineering planning and physical site execution:

* **Planned Schedules**: Built and maintained in Oracle Primavera P6 or Microsoft Project with formal Work Breakdown Structures (WBS), Critical Path Method (CPM) precedence relationships, target dates, and explicit activity codes (e.g., `CIV-1001`).
* **Field Execution**: Arrives from heterogeneous, unstructured, or semi-structured sources: daily site progress reports, contractor spreadsheets, supervisor shift logs, conversational voice notes, and inspection memos.

Field narratives describe work naturally (e.g., *"Completed foundation pour for F-204 and stripped formwork"* or *"Installed 120m of 4-inch underground piping on Rack B"*), rarely citing exact P6 activity codes. Consequently, project teams face:

1. **Fragmented actual-progress data**: Information trapped in disconnected PDFs, chat threads, and emails.
2. **Manual reconciliation bottleneck**: Planners spending hours cross-referencing field reports against thousands of schedule line items.
3. **Delayed schedule cadence**: Updates occurring weekly or monthly, rendering critical path analysis retrospective rather than proactive.
4. **Weak traceability and auditability**: Inability to demonstrate which field document, photo, or supervisor report authorized a specific percent-complete modification.
5. **Loss of institutional memory**: When projects close, observed production rates, actual crew productivities, and duration variances are abandoned in static archives rather than informing future project baselines.

### Scope Distinction
* **SIH26122**: The competitive problem statement addressing automated schedule updating from field reports.
* **ScheduleManager**: The complete implemented platform that ingests schedules, normalizes field evidence, matches activities, enforces human confirmation governance, and exposes historical performance intelligence.
* **Time Agent**: A conversational subsystem within ScheduleManager enabling supervisors to report progress, receive targeted clarification prompts, and stage update proposals.

ScheduleManager is **not** a generic chatbot, a RAG wrapper, or an autonomous CPM rescheduler. It is a **governed planning-to-execution reconciliation and intelligence bridge**.

---

## 2. High-Level Solution

ScheduleManager organizes data flow into two operational loops: the **Active Execution Loop** and the **Historical Memory Loop**.

### Active Execution Event Pipeline
```mermaid
flowchart TD
    P6["Primavera P6 XER / XML / CSV / XLSX"] --> P["Document Parser Service (Port 8001)"]
    P --> C["Canonical Schedule Representation"]
    C --> DB[("PostgreSQL Database (Port 5432)")]

    F["Field Reports / Spreadsheets / Conversations"] --> X["MinIO Storage + Extraction Engine"]
    X --> E["ExecutionEvent (Structured with Lineage)"]
    DB -.->|"Candidate Scope"| M["Candidate Retrieval"]
    E --> M
    M --> S["Multi-Signal Matching Engine"]
    S --> G{"Confidence Routing"}
    G -->|"Score >= 0.85 & Margin >= 0.15"| A["AUTO_LINK Candidate"]
    G -->|"Score >= 0.50 & Ambiguous"| R["PLANNER_REVIEW (Queue / Time Agent)"]
    G -->|"Score < 0.50"| U["UNMATCHED Status"]

    A --> PROP["Stage Persistent UpdateProposal"]
    R --> PROP
    PROP --> CONF["Explicit Human Confirmation"]
    CONF --> SUS["ScheduleUpdateService\n(Row-Locked Atomic Transaction)"]
    SUS --> MUT["Activity Progress Mutation\n(CPM Firewall Preserved)"]
    SUS --> LEDG["ActualProgressLedger\n(Append-Only Historical Entry)"]
    SUS --> AUD["ScheduleAuditLog\n(Full Provenance to Artifact / MinIO)"]
    SUS --> OUT["DomainOutbox Dispatch\n(PROGRESS_UPDATED Event)"]
```

### Historical Memory Loop
```mermaid
flowchart TD
    VERIF["Verified Execution Records in ActualProgressLedger"] --> HAS["HistoricalAnalyticsService\n(Deterministic PostgreSQL Math)"]
    HAS --> PROD["Observed Productivity Rates\n(Total Qty / Distinct Reporting Days)\nStrictly Isolated by Compatible Unit"]
    HAS --> DUR["Planned vs Actual Durations\n(Calendar Days Variance for Completed Activities)"]
    HAS --> BENCH["Advisory Planning Benchmarks\n(Sample Size Validation: N >= 3, P50/P80 when N >= 5)"]

    PROD --> IMS["InstitutionalMemoryService"]
    DUR --> IMS
    BENCH --> IMS

    IMS --> TAB["Institutional Memory Workspace\n(Overview, Productivity, Durations, Ledger, Query)"]
    IMS --> DRAWER["Evidence Lineage Drawer\n('Where did this number come from?')"]
    IMS --> CSV["RFC 4180 CSV Ledger Export"]
    IMS --> AGENT_TOOL["Time Agent Historical Query Tool\n(Grounded in Deterministic PostgreSQL Metrics)"]
```

---

## 3. System Architecture

ScheduleManager is built on an asynchronous, multi-service architecture running in Docker:

```mermaid
flowchart TB
    subgraph Client ["Frontend Layer (Port 3000)"]
        UI["Next.js 14 App Router (TypeScript + Tailwind)"]
        Tab1["Project Overview & KPIs"]
        Tab2["Interactive WBS Hierarchy"]
        Tab3["Activity Grid (Sort/Filter/Page)"]
        Tab4["Gantt Chart (CPM Precedence)"]
        Tab5["Field Reports & Review Queue"]
        Tab6["Time Agent Chat (Project-Scoped)"]
        Tab7["Institutional Memory Workspace"]
        UI --- Tab1 & Tab2 & Tab3 & Tab4 & Tab5 & Tab6 & Tab7
    end

    subgraph Backend ["Backend API Service (Port 8080)"]
        API["FastAPI Application"]
        RouterProj["/projects Router"]
        RouterAct["/activities & /wbs Router"]
        RouterArt["/artifacts Router"]
        RouterMatch["/matching Router"]
        RouterRev["/review Router"]
        RouterAgent["/agent Router"]
        RouterMem["/institutional-memory Router"]
        RouterExp["/export Router"]

        API --> RouterProj & RouterAct & RouterArt & RouterMatch & RouterRev & RouterAgent & RouterMem & RouterExp

        subgraph CoreServices ["Core Business Services"]
            SUpdate["ScheduleUpdateService\n(Idempotent Progress & Invariant Guard)"]
            SMatch["MatchingService\n(Multi-Signal Scoring & Routing)"]
            SExtract["ExtractionService\n(Gemini 3.5 Flash / Rule Fallbacks)"]
            SAgent["TimeAgentService\n(Conversational Lifecycle & Proposal Staging)"]
            SParser["ConversationalParser\n(Deterministic Date & Bulk Intent)"]
            SAnalytics["HistoricalAnalyticsService\n(SQL Aggregation & Benchmark Rules)"]
            SMemory["InstitutionalMemoryService\n(Query Engine & CSV Exporter)"]
            SMinIO["MinIOService\n(Object Storage & Presigned URLs)"]
            SXer["XERExportService\n(P6 XER Generator)"]
        end

        RouterAgent --> SAgent & SParser
        RouterMatch --> SMatch
        RouterArt --> SExtract & SMinIO
        RouterRev --> SUpdate
        RouterAgent --> SUpdate
        RouterMem --> SAnalytics & SMemory
        RouterExp --> SXer
    end

    subgraph ParserService ["Document Parser Microservice (Port 8001)"]
        FastParser["FastAPI + Pydantic + openpyxl + defusedxml"]
        P_XER["XER Relational Block Parser (%T, %F, %R, %E)"]
        P_XML["P6 XML Hierarchical Schema Parser"]
        P_CSV["CSV Column Normalizer"]
        P_XLSX["Multi-Sheet Excel Normalizer"]
        FastParser --> P_XER & P_XML & P_CSV & P_XLSX
    end

    subgraph DataStorage ["Storage & Persistence Layer"]
        PG[("PostgreSQL 16 Alpine (Port 5432)\n13 Relational Tables\nAppend-Only Ledgers & Outbox")]
        MinIO[("MinIO S3 Storage (Port 9000/9001)\nBucket: sih-artifacts\nOriginal Binary Evidence")]
    end

    subgraph AI ["AI Intelligence Layer (Google Gemini)"]
        GeminiAgent["gemini-2.5-flash\n(Conversational Intent & Proposal Structuring)"]
        GeminiExtract["gemini-3.5-flash\n(Field Document & Narrative Extraction)"]
    end

    UI -->|"HTTP / JSON (REST)"| API
    RouterProj -->|"Multipart Stream"| FastParser
    CoreServices -->|"SQLAlchemy 2.0 ORM"| PG
    SMinIO -->|"S3 API (MinIO Client)"| MinIO
    SAgent -.->|"TIME_AGENT_GEMINI_API_KEY"| GeminiAgent
    SExtract -.->|"EXTRACTION_GEMINI_API_KEY"| GeminiExtract
```

### Services & Container Topology

| Service Name | Container Name | Port Mapping | Image / Build | Core Responsibility |
| :--- | :--- | :--- | :--- | :--- |
| **`frontend`** | `primavera-frontend` | `3000:3000` | `./frontend` (Next.js 14, React 18, TypeScript) | Project dashboard, Gantt timeline, review queue, Time Agent interface, Institutional Memory workspace |
| **`backend`** | `primavera-backend` | `8080:8000` | `./backend` (FastAPI, SQLAlchemy 2.0, Python 3.12) | Core REST API, matching engine, update governance, Time Agent coordinator, historical analytics |
| **`document-parser`** | `primavera-document-parser` | `8001:8001` | `./document-parser` (FastAPI, openpyxl, defusedxml) | Autonomous parser normalizing `.xer`, `.xml`, `.csv`, and `.xlsx` schedules to canonical JSON |
| **`postgres`** | `primavera-postgres` | `5432:5432` | `postgres:16-alpine` | Relational database (source of truth for schedules, execution events, ledgers, audit trail) |
| **`minio`** | `primavera-minio` | `9000:9000`<br>`9001:9001` | `quay.io/minio/minio:latest` | S3-compatible permanent artifact storage (raw PDFs, spreadsheets, audio memos, images) |

---

## 4. Distinction of Core Concepts & Memory Types

A foundational principle of ScheduleManager is the strict architectural separation of state and memory:

```mermaid
classDiagram
    class ConversationHistory {
        +UUID conversation_id
        +UUID project_id
        +String user_id
        +List messages
        +UUID active_event_id
        +Int clarification_turns
        Scope: Project-isolated chat session
        Lifecycle: Ephemeral/Session-based
        Purpose: Human-agent communication
    }

    class ScheduleState {
        +UUID project_id
        +List activities
        +List wbs_nodes
        +List relationships
        +Float percent_complete
        +DateTime actual_start
        +DateTime actual_finish
        Scope: Current live project schedule
        Lifecycle: Mutated only via explicit confirmation
        Purpose: Active project tracking & CPM calculation
    }

    class InstitutionalMemory {
        +UUID ledger_id
        +Float installed_quantity
        +String unit_of_measure
        +Float observed_rate
        +Float duration_variance
        +PlanningBenchmark advisory_benchmark
        Scope: Historical verified execution knowledge
        Lifecycle: Immutable, append-only historical database
        Purpose: Cross-shift analytics & future project estimation
    }

    ConversationHistory ..> ScheduleState : Stages proposals for
    ScheduleState ..> InstitutionalMemory : Feeds verified actuals into
```

### 1. Conversation History (Project-Scoped)
* **What it is**: Messages exchanged between a user (e.g., site supervisor) and the Time Agent in a specific project chat.
* **Storage**: `conversations` and `conversation_messages` tables.
* **Scope**: Strictly scoped to `project_id`. Starting a new chat creates a new conversation; past conversations can be revisited. Conversations do **not** leak between projects.
* **Boundary**: Separate conversations do not inherit active event state from each other. Conversation history is **not** institutional memory.

### 2. Schedule State (Live Operational State)
* **What it is**: The current authoritative operational status of activities, WBS nodes, CPM dependencies, percent completes, and actual dates.
* **Storage**: `activities`, `wbs`, `activity_relationships`, and `projects` tables.
* **Boundary**: The LLM cannot mutate schedule state directly. Schedule state is only updated through `ScheduleUpdateService` following explicit human confirmation.

### 3. Institutional Memory (Verified Historical Intelligence)
* **What it is**: Platform-level historical execution knowledge built from verified, applied progress records across completed and ongoing work.
* **Storage**: `actual_progress_ledger`, joined with `execution_events`, `activities`, and `artifacts`.
* **Computation**: Pure PostgreSQL aggregation (deterministic SQL math). The LLM does **not** compute, invent, or hallucinate historical metrics.
* **Boundary**: Institutional Memory is read-only and analytical. It provides advisory planning benchmarks and observed production rates to planners and the Time Agent.

---

## 5. Authoritative Data Model

The PostgreSQL relational schema contains exactly 13 domain models (`backend/app/domain/models.py`). There are no fictitious tables (e.g., no `ScheduleVersion`, `DelayEvent`, or `ProductivityMetric` tables):

```mermaid
erDiagram
    PROJECTS ||--o{ WBS : contains
    PROJECTS ||--o{ ACTIVITIES : contains
    PROJECTS ||--o{ ACTIVITY_RELATIONSHIPS : contains
    PROJECTS ||--o{ ARTIFACTS : contains
    PROJECTS ||--o{ EXECUTION_EVENTS : contains
    PROJECTS ||--o{ CONVERSATIONS : owns
    PROJECTS ||--o{ UPDATE_PROPOSALS : owns
    PROJECTS ||--o{ ACTUAL_PROGRESS_LEDGER : tracks
    PROJECTS ||--o{ SCHEDULE_AUDIT_LOG : audits

    WBS ||--o{ WBS : "parent/child"
    WBS ||--o{ ACTIVITIES : groups

    ACTIVITIES ||--o{ ACTIVITY_RELATIONSHIPS : "predecessor"
    ACTIVITIES ||--o{ ACTIVITY_RELATIONSHIPS : "successor"
    ACTIVITIES ||--o{ EXECUTION_EVENTS : "matched_activity"
    ACTIVITIES ||--o{ ACTUAL_PROGRESS_LEDGER : records
    ACTIVITIES ||--o{ SCHEDULE_AUDIT_LOG : logs

    ARTIFACTS ||--o{ EXECUTION_EVENTS : generates
    ARTIFACTS ||--o{ SCHEDULE_AUDIT_LOG : referenced_by

    CONVERSATIONS ||--o{ CONVERSATION_MESSAGES : contains
    CONVERSATIONS ||--o{ EXECUTION_EVENTS : tracks
    CONVERSATIONS ||--o{ UPDATE_PROPOSALS : contains

    EXECUTION_EVENTS ||--o| REVIEW_DECISIONS : receives
    EXECUTION_EVENTS ||--o{ ACTUAL_PROGRESS_LEDGER : materializes
    EXECUTION_EVENTS ||--o{ UPDATE_PROPOSALS : targets
    EXECUTION_EVENTS ||--o{ SCHEDULE_AUDIT_LOG : audited_in
```

### Implemented Model Specifications

| Model Name | Table Name | Key Attributes & Fields | Operational Role |
| :--- | :--- | :--- | :--- |
| **`Project`** | `projects` | `id`, `project_code`, `name`, `planned_start`, `planned_finish`, `data_date`, `created_at`, `updated_at` | Top-level project container anchoring all schedule and execution data. |
| **`WBSNode`** | `wbs` | `id`, `project_id`, `parent_id`, `code`, `name` | Hierarchical Work Breakdown Structure tree supporting parent-child recursion. |
| **`Activity`** | `activities` | `id`, `project_id`, `wbs_id`, `activity_code`, `name`, `activity_type`, `status`, `planned_start`, `planned_finish`, `actual_start`, `actual_finish`, `original_duration`, `remaining_duration`, `percent_complete`, `planned_quantity`, `quantity_unit`, `discipline`, `location_code`, `contractor_name` | The primary schedule element representing a unit of work. Planned dates are protected by the CPM firewall. |
| **`ActivityRelationship`** | `activity_relationships` | `id`, `project_id`, `predecessor_id`, `successor_id`, `relationship_type` (`FS`, `SS`, `FF`, `SF`), `lag` | Precedence logic driving CPM calculations. Validates against self-reference and duplicates. |
| **`Artifact`** | `artifacts` | `id`, `project_id`, `report_id`, `artifact_type`, `original_filename`, `mime_type`, `size_bytes`, `sha256`, `storage_bucket`, `storage_key`, `uploaded_by`, `extraction_status` | Permanent metadata for field files stored in MinIO. Enforces SHA-256 deduplication. |
| **`ExecutionEvent`** | `execution_events` | `id`, `project_id`, `artifact_id`, `conversation_id`, `message_id`, `source_type`, `verbatim_excerpt`, `reported_activity_code`, `description`, `execution_date`, `status_reported`, `quantity`, `unit`, `location`, `discipline`, `contractor`, `wbs_hint`, `extraction_confidence`, `status`, `matched_activity_id`, `match_score`, `match_metadata` | Structured representation of a physical site event extracted from field evidence or conversation. |
| **`ReviewDecision`** | `review_decisions` | `id`, `execution_event_id`, `project_id`, `activity_id`, `reviewer_id`, `decision` (`APPROVED`, `REJECTED`, `REASSIGNED`), `adjustment_percent`, `notes`, `reviewed_at` | Planner human-in-the-loop decision record resolving ambiguous execution events. |
| **`ActualProgressLedger`** | `actual_progress_ledger` | `id`, `project_id`, `activity_id`, `execution_event_id`, `reporting_date`, `installed_quantity`, `unit_of_measure`, `incremental_percent`, `cumulative_percent`, `created_at` | **Authoritative append-only historical ledger**. Records every applied physical increment. Foundation for Institutional Memory. |
| **`ScheduleAuditLog`** | `schedule_audit_log` | `id`, `project_id`, `activity_id`, `execution_event_id`, `artifact_id`, `action`, `previous_state`, `new_state`, `user_id`, `timestamp` | Immutable audit log capturing full JSON snapshots of previous and mutated states with complete evidence provenance. |
| **`DomainOutbox`** | `domain_outbox` | `id`, `event_type`, `aggregate_id`, `payload`, `status` (`PENDING`, `PROCESSED`, `FAILED`), `created_at`, `processed_at` | Transactional outbox table for reliable external event propagation and webhook dispatch. |
| **`Conversation`** | `conversations` | `id`, `project_id`, `title`, `user_id`, `active_activity_id`, `active_event_id`, `clarification_turns`, `status` (`ACTIVE`, `WAITING_FOR_USER`, `RESOLVED`, `ABANDONED`) | Project-scoped chat session tracking in-flight multi-turn dialog and active draft events. |
| **`ConversationMessage`** | `conversation_messages` | `id`, `conversation_id`, `sender` (`USER`, `AGENT`, `SYSTEM`), `content`, `message_metadata`, `created_at` | Individual chat message with optional structured metadata (cards, candidate lists, actions). |
| **`UpdateProposal`** | `update_proposals` | `id`, `conversation_id`, `event_id`, `project_id`, `matched_activity_id`, `proposed_state`, `baseline_activity_state`, `status` (`PENDING`, `CONFIRMED`, `CONSUMED`, `REJECTED`, `EXPIRED`), `expires_at`, `confirmed_by`, `confirmed_at` | Ephemeral, staged update proposal requiring explicit user confirmation before schedule mutation. |

---

## 6. Schedule Ingestion & P6 Interoperability

ScheduleManager ingests schedules via the dedicated `document-parser` microservice (`port 8001`) and persists them relationally in PostgreSQL.

### Supported Schedule Formats
1. **Primavera P6 `.xer` (Implemented)**: Parses relational export tables: `%T PROJECT`, `%T PROJWBS`, `%T TASK`, and `%T TASKPRED`. Extracts dates, durations, physical percent completes, and precedence links with lags.
2. **Primavera P6 `.xml` (Implemented)**: Hierarchical XML schema parser resolving `<Project>`, `<WBS>`, `<Activity>`, and `<Relationship>` elements with namespace tolerance.
3. **Primavera `.csv` (Implemented)**: Header-aware CSV parser mapping standard P6 columns (`Activity ID`, `Activity Name`, `WBS`, `Status`, `Start`, `Finish`, `Duration`, `% Complete`, `Predecessors`).
4. **Excel `.xlsx` (Implemented)**: Multi-sheet workbook parser supporting the same column aliases as CSV.
5. **Microsoft Project (`.mpp` / MS Project XML)**: **Not implemented** in the current codebase. (All schedule processing is centered on Primavera P6 XER/XML and standardized spreadsheets).

### Canonical Schedule Representation
The parser normalizes all input formats into a standardized JSON payload prior to database insertion:
```json
{
  "project": {
    "project_code": "BOROUGE4_DEMO",
    "name": "Borouge 4 Polyolefin Expansion Project",
    "planned_start": "2024-01-01T08:00:00",
    "planned_finish": "2025-12-31T17:00:00",
    "data_date": "2024-01-01T08:00:00"
  },
  "wbs": [
    { "code": "WBS.1", "name": "Civil Works", "parent_code": null },
    { "code": "WBS.1.1", "name": "Foundations", "parent_code": "WBS.1" }
  ],
  "activities": [
    {
      "activity_code": "CIV-1001",
      "name": "Foundation Pour Area F-204",
      "wbs_code": "WBS.1.1",
      "activity_type": "TT_Task",
      "status": "NOT_STARTED",
      "planned_start": "2024-01-10T08:00:00",
      "planned_finish": "2024-01-20T17:00:00",
      "original_duration": 10.0,
      "remaining_duration": 10.0,
      "percent_complete": 0.0,
      "planned_quantity": 250.0,
      "quantity_unit": "m3",
      "calendar": "Standard 5 Day"
    }
  ],
  "relationships": [
    {
      "predecessor_code": "CIV-1001",
      "successor_code": "CIV-1002",
      "relationship_type": "FS",
      "lag": 0.0
    }
  ]
}
```

### Primavera P6 XER Export
ScheduleManager supports export back to native Primavera P6 XER format (`GET /api/v1/projects/{project_id}/export/xer`). The export dynamically generates `%T PROJECT` and `%T TASK` records with updated statuses (`TK_Complete`, `TK_Active`, `TK_NotStart`), actual start/finish timestamps, and physical percent completes reflecting applied field progress.

*Fidelity Note*: The current XER generator exports core schedule progress tables (`PROJECT`, `TASK`). Advanced P6 features such as resource assignments (`TASKRSRC`), cost accounts, and notebook topics are preserved in incoming files if re-exported through passthrough, but are not independently modeled in the relational schema.

---

## 7. Field Ingestion & Execution Event Model

Field progress evidence is uploaded via multipart form requests (`POST /api/v1/projects/{project_id}/artifacts/upload`) or directly through the Time Agent chat interface.

### Supported Field Evidence Formats
* **PDF Documents**: Daily progress reports, inspection certificates, shift summaries. Extracted using `pypdf` and LLM vision/text structuring.
* **Spreadsheets (`.xlsx`, `.xls`, `.csv`)**: Contractor quantity tracking sheets and daily log tables.
* **Text / Conversational Messages**: Supervisor field updates submitted in natural language.
* **Audio Voice Memos (`.m4a`, `.mp3`, `.wav`)**: 
  > [!NOTE]
  > **Audio Implementation Status**: Audio voice memos are uploaded, hashed via SHA-256, permanently stored in MinIO object storage, and cataloged in the `artifacts` table as evidence. **Live speech-to-text transcription is deferred to future work.** Text extraction from voice memos currently creates an evidence artifact record; transcription must be supplied via text or companion field notes.

### Execution Event Schema (`ExecutionEvent`)
An `ExecutionEvent` represents an atomic physical occurrence extracted from field evidence:
* `source_type`: `ARTIFACT`, `CONVERSATION`, or `HYBRID`.
* `verbatim_excerpt`: Exact raw text snippet from the field report or user utterance justifying the event.
* `reported_activity_code`: Explicit code if cited by the supervisor (e.g., `CIV-1001`), otherwise `null`.
* `description`: Concise normalized summary of physical work executed.
* `execution_date`: Deterministically resolved date of work.
* `quantity` & `unit`: Measured physical output (e.g., `35.0` `m3`, `120.0` `m`).
* `location`: Physical tag, gridline, or foundation (e.g., `F-204`, `Rack B`).
* `discipline`: Engineering domain (e.g., `Civil`, `Piping`, `Electrical`, `Structural`).
* `contractor`: Performing subcontractor or work crew.
* `extraction_confidence`: Confidence score (0.0–1.0) assigned by the extraction model.
* `status`: `DRAFT`, `UNMATCHED`, `IN_REVIEW`, `AUTO_LINKED`, `APPLIED`, or `REJECTED`.

---

## 8. Deterministic Multi-Signal Matching Engine

When an `ExecutionEvent` is created, the `MatchingService` evaluates candidate schedule activities using a deterministic multi-signal scoring algorithm.

### Scoring Signals
1. **Exact Code Signal ($S_{id}$)**: Returns `1.0` if the reported code matches `activity.activity_code` or appears verbatim in the narrative; otherwise `0.0`.
2. **Text Similarity ($S_{text}$)**: Hybrid token coverage (75%) and Jaccard similarity (25%) comparing the event description against the activity name.
3. **WBS & Hierarchy Alignment ($S_{wbs}$)**: Evaluates match between the event WBS hint/location and the activity WBS node name or discipline ($0.50$–$1.00$).
4. **Temporal Compatibility ($S_{temp}$)**: Evaluates execution date relative to planned start/finish window:
   * Event within planned window: $1.00$
   * $\le 7$ days delta: $0.80$
   * $\le 14$ days delta: $0.60$
   * $\le 30$ days delta: $0.40$
   * $> 30$ days delta: $0.10$
5. **Contextual Alignment ($S_{context}$)**: Evaluates matches on location code ($1.00$) and contractor name ($\pm 0.20$).

### Mathematical Weighting Formulas

#### Case A: Explicit Activity Code Present ($S_{id} = 1.0$)
$$S_{total} = \max\left(0.95,\, 0.40 S_{id} + 0.30 S_{text} + 0.15 S_{wbs} + 0.10 S_{temp} + 0.05 S_{context}\right)$$
*(An exact activity code match guarantees an overall match score of at least 0.95).*

#### Case B: No Activity Code Cited ($S_{id} = 0.0$)
$$S_{total} = 0.45 S_{text} + 0.25 S_{wbs} + 0.15 S_{temp} + 0.15 S_{context}$$

### Confidence Routing Policy
Scored candidates are ranked by $S_{total}$. Let $C_1$ be the top candidate and $C_2$ be the second candidate. The margin delta is defined as:
$$\Delta_{margin} = S_{total}(C_1) - S_{total}(C_2)$$

* **`AUTO_LINK`**: Routed automatically to proposal staging or progress update **only** if:
  $$S_{total}(C_1) \ge 0.85 \quad \text{AND} \quad \Delta_{margin} \ge 0.15 \quad \text{AND} \quad \text{extraction\_confidence} \ge 0.80$$
* **`PLANNER_REVIEW`**: If $S_{total}(C_1) \ge 0.50$ but the auto-link margin is not satisfied (ambiguous candidates), the event is set to `IN_REVIEW` and routed to the Lead Planner Review Queue or Time Agent clarification.
* **`UNMATCHED`**: If $S_{total}(C_1) < 0.50$, the event is marked `UNMATCHED`.

*ScheduleManager does not claim 100% autonomous accuracy; it relies on deterministic confidence routing with explicit human confirmation boundaries.*

---

## 9. Time Agent

The **Time Agent** is an interactive, conversational subsystem allowing site personnel to report progress, answer targeted clarification questions, and query project execution data using natural language.

### Supported Intent Classes (`agent_parser.py`)
1. **`INFORMATION_QUERY`**: Inquiries regarding activity dates, remaining duration, status, or historical performance.
2. **`PROGRESS_REPORT`**: Narrative describing physical construction work for a specific activity (e.g., *"Poured 35 m3 concrete for F-204"*).
3. **`PROGRESS_UPDATE_REQUEST`**: Direct request to set status or percent complete (e.g., *"Update CIV-1001 to 80%"*).
4. **`CLARIFICATION_RESPONSE`**: Answering an agent question with a specific code, date, or quantity semantics choice.
5. **`ARTIFACT_SUBMISSION`**: Attaching a field document or photo to the chat session.
6. **`BULK_PROGRESS_REPORT`**: Reporting progress across a group of activities, discipline, or work package (e.g., *"Completed all electrical activities"*).

### Agent Architecture & Governance Boundary
```mermaid
flowchart TD
    UM["User Natural Language Message / File Upload"] --> PARSER["ConversationalParser\n(Gemini 2.5 Flash / Rule Fallbacks)"]
    PARSER --> INTENT{"Intent Classification"}

    INTENT -->|"INFORMATION_QUERY"| IQ["Execute Historical Analytics / DB Query"]
    IQ --> RESP["Authoritative Answer Grounded in PostgreSQL"]

    INTENT -->|"PROGRESS_REPORT / UPDATE"| DRAFT["Create or Enrich Draft ExecutionEvent"]
    INTENT -->|"BULK_PROGRESS_REPORT"| BULK["Authoritative PostgreSQL Scope Resolution"]

    DRAFT --> EVAL["MatchingService.evaluate_event_for_agent()"]
    EVAL --> ROUTE{"Match Confidence"}

    ROUTE -->|"High Confidence (AUTO_LINK)"| STAGE["Stage Persistent UpdateProposal in PostgreSQL"]
    STAGE --> CARD["Action Card: Proposal Confirmation in Chat"]
    CARD --> CONF_ACT{"User Confirmation Action"}
    CONF_ACT -->|"Confirm"| EXEC["ScheduleUpdateService Mutation\n(Row Lock + Invariant Check)"]
    CONF_ACT -->|"Reject"| REJ["Mark Proposal REJECTED"]

    ROUTE -->|"Ambiguous (2 candidates)"| AB["Pairwise A/B Clarification Card\n(Candidate 1 / Candidate 2 / None of these)"]
    ROUTE -->|"Ambiguous (3-4 candidates)"| LIST["Candidate List Clarification Card\n(Ranked Options + None of these)"]
    ROUTE -->|"Clarification Turns >= 3"| ESCALATE["Route to Lead Planner Review Queue (IN_REVIEW)"]

    AB --> ANS["User Clarification Answer"]
    LIST --> ANS
    ANS --> DRAFT

    BULK --> BULK_PREVIEW["Action Card: Bulk Scope Proposal Preview"]
    BULK_PREVIEW --> BULK_ACT{"User Bulk Confirmation"}
    BULK_ACT -->|"Confirm All"| BULK_EXEC["Atomic Multi-Activity Mutation"]
    BULK_ACT -->|"Cancel"| BULK_CANCEL["Cancel Bulk Action"]
```

> [!IMPORTANT]
> **Governance Firewall**: The LLM interprets natural language, but **never** directly updates the database or schedule. The backend MatchingService identifies candidate activities, the backend stages a persistent `UpdateProposal`, and the user must explicitly confirm the action before `ScheduleUpdateService` executes the mutation.

### Dynamic Multi-Choice Clarification
When an update is ambiguous, the Time Agent generates targeted interactive options:
* **Pairwise A/B Clarification**: When exactly two meaningful candidates compete (e.g., `CIV-1004` vs `CIV-1005`), the agent asks:
  > *"Did this work apply to CIV-1004 (Foundation Pour F-204) or CIV-1005 (Foundation Pour F-205)?"*
  Options presented: `[CIV-1004 - Foundation Pour F-204]` | `[CIV-1005 - Foundation Pour F-205]` | `[None of these]`.
* **Structured Candidate List**: When 3–4 candidates exist with scores $\ge 0.25$, the agent displays an interactive list with match confidence percentages and a mandatory `[None of these]` option.
* **Clarification Turn Governance**: If ambiguity persists after **3 clarification turns**, the agent ceases questioning and routes the event to the Lead Planner Review Queue (`IN_REVIEW`).

---

## 10. Governed Bulk Intent

ScheduleManager provides governed bulk-progress updates for work package completions (e.g., *"We completed all the electrical activities"* or *"Finished cable tray installations on Level 2"*):

```mermaid
sequenceDiagram
    autonumber
    actor Supervisor as Site Supervisor
    participant Agent as Time Agent UI
    participant Parser as ConversationalParser
    participant DB as PostgreSQL Database
    participant Svc as ScheduleUpdateService

    Supervisor->>Agent: "We completed all the electrical activities"
    Agent->>Parser: Parse utterance
    Parser-->>Agent: Intent: BULK_PROGRESS_REPORT, Scope: {discipline: "Electrical"}, Status: COMPLETED
    Agent->>DB: Authoritative query: Active activities WHERE discipline = 'Electrical'
    DB-->>Agent: Returns 4 matching activities (ELE-1001 to ELE-1004)
    Agent-->>Supervisor: Displays BULK_SCOPE_PROPOSAL Action Card with 4-activity preview table
    Supervisor->>Agent: Clicks "Update All 4 to 100%"
    Agent->>Svc: POST /agent/conversations/{id}/bulk-confirm
    Note over Svc,DB: Atomic Transaction: Updates 4 activities, creates 4 ledger rows, writes 4 audit logs
    Svc-->>Agent: Success confirmation (4 activities updated)
    Agent-->>Supervisor: "Successfully updated 4 electrical activities to 100% complete."
```

### Safety & Integrity Rules for Bulk Updates
1. **No LLM Membership Decision**: The LLM extracts the search scope; **PostgreSQL authoritatively resolves the matching activities**.
2. **Preview Before Mutation**: The user is presented with a preview card displaying each activity code, name, current percent, and target percent.
3. **Threshold Partitioning**:
   * **1 activity matched**: Automatically converted to a standard single-activity proposal card.
   * **2–6 activities matched**: Displays multi-item confirmation card with option to update all or select an individual activity.
   * **> 6 activities matched**: Broad work package protection triggers. The agent displays a summary of the first 5 activities and requires the user to review the activities in the main schedule table rather than executing blind chat updates.
4. **Atomic Transaction**: Bulk confirmations execute in a single PostgreSQL transaction; if any activity update fails validation, the entire batch rolls back.

---

## 11. Progress Semantics & Schedule Update Governance

Schedule updates are governed by strict engineering invariants enforced in `ScheduleUpdateService.py`.

### Quantity Semantics
* **Incremental Semantics (`INCREMENTAL`)**: Work installed during the reported shift or day (e.g., `+35 m3`).
  $$\text{New Percent} = \min\left(100.0,\, \text{Previous Percent} + \frac{\text{Installed Quantity}}{\text{Planned Quantity}} \times 100\right)$$
* **Cumulative Semantics (`CUMULATIVE`)**: Total quantity installed to date (e.g., `180 m3 of 250 m3 total`).
  $$\text{New Percent} = \min\left(100.0,\, \frac{\text{Reported Cumulative Quantity}}{\text{Planned Quantity}} \times 100\right)$$
  *Monotonicity Enforcement*: If a reported cumulative quantity is less than previously recorded installed quantity, the update is rejected with a `422 Unprocessable Entity` validation error.
* **Direct Percent Override**: Explicit percentage provided by an authorized planner (e.g., `80%`).

### Critical Path Method (CPM) Protection Firewall
The `ScheduleUpdateService` strictly enforces separation between baseline planning logic and actual progress:
* **Mutated Fields**: `percent_complete`, `status` (`IN_PROGRESS`, `COMPLETED`), `actual_start`, `actual_finish`.
* **Protected Fields**: `planned_start`, `planned_finish`, `original_duration`, calendar assignments, and CPM logic relationships are **immutable** during field execution updates. They cannot be overwritten by field reports.

### Governance & Mutation Pipeline
```mermaid
flowchart TD
    TRIGGER["Update Trigger\n(Time Agent Confirmation / Lead Planner Decision)"] --> VAL["ValidationService\n(Schema, Monotonicity & Precedence Check)"]
    VAL --> LOCK["SELECT FOR UPDATE\n(Row-Level Lock on Target Activity)"]

    subgraph AtomicTx ["ScheduleUpdateService Atomic Transaction"]
        direction TB
        CHECK_SEM["Resolve Semantics\n(INCREMENTAL vs CUMULATIVE vs Percent Override)"]
        CALC_PCT["Compute New Cumulative Percent Complete\n(Bounded strictly 0.0% to 100.0%)"]
        CALC_DATES["Derive actual_start / actual_finish\n(Strictly Preserve planned_start & finish)"]
        INS_LEDG["Insert into actual_progress_ledger\n(installed_quantity, unit, dates)"]
        MUT_ACT["Mutate Activity State\n(percent_complete, status, actual dates)"]
        INS_AUD["Insert into schedule_audit_log\n(JSON previous/new state, user, artifact lineage)"]
        INS_OUT["Insert into domain_outbox\n(PROGRESS_UPDATED event payload)"]

        CHECK_SEM --> CALC_PCT --> CALC_DATES --> INS_LEDG --> MUT_ACT --> INS_AUD --> INS_OUT
    end

    LOCK --> AtomicTx
    AtomicTx --> COMMIT["Commit Transaction"]
    COMMIT --> LIVE_UI["Real-Time UI Updates\n(Activities Grid, Gantt Shading, Memory Ledger)"]
    COMMIT --> XER_READY["P6 XER Export Synchronized"]
```

---

## 12. Actual Progress Ledger & Audit Trail

### Actual Progress Ledger (`actual_progress_ledger`)
The `actual_progress_ledger` table is an **append-only historical record** of verified physical progress. Every approved execution update inserts a permanent ledger entry:
* `id`: Unique UUID.
* `project_id`: Project identifier.
* `activity_id`: Target activity.
* `execution_event_id`: Source execution event.
* `reporting_date`: Date the physical work was executed.
* `installed_quantity`: Physical quantity installed during the reporting window.
* `unit_of_measure`: Standard engineering unit (`m3`, `m`, `t`, `ea`).
* `incremental_percent`: Percentage gain resulting from this specific update.
* `cumulative_percent`: Resulting total progress percentage.

*Significance*: This ledger is the mathematical foundation for Institutional Memory.

### Schedule Audit Log (`schedule_audit_log`)
Every state mutation generates an immutable audit record containing:
* `previous_state`: Full JSON snapshot of activity attributes before mutation.
* `new_state`: Full JSON snapshot of activity attributes after mutation.
* `action`: Action descriptor (e.g., `AGENT_PROPOSAL_CONFIRMED`, `BULK_PROPOSAL_CONFIRMED`, `PLANNER_REVIEW_APPROVED`).
* `user_id`: Authenticated user or caller ID responsible for the confirmation.
* `execution_event_id` & `artifact_id`: Foreign key lineage linking directly back to the original source file and MinIO storage key.

---

## 13. Institutional Memory Engine V1

**Institutional Memory** transforms verified historical project records into reusable, queryable performance intelligence.

```mermaid
flowchart TD
    LEDGER[("actual_progress_ledger\n(Verified Append-Only History)")] --> HAS["HistoricalAnalyticsService\n(Pure PostgreSQL SQL Aggregations)"]

    HAS --> PROD["Observed Productivity Rates\n(Total Installed Qty / Distinct Reporting Days)\nStrictly Isolated by Unit"]
    HAS --> DUR["Planned vs Actual Durations\n(Variance Days = Actual Days - Planned Days)\nCompleted Activities Only"]
    HAS --> BENCH{"Benchmark Sample Check\n(Completed N >= 3)"}

    BENCH -->|"N < 3"| SPARSE["INSUFFICIENT_SAMPLE\n(Observed Rate Caveat, No Baseline)"]
    BENCH -->|"N >= 3"| VALID["SUFFICIENT_SAMPLE\n(Median, Mean, P50 & P80 when N >= 5)"]

    PROD --> IMS["InstitutionalMemoryService"]
    DUR --> IMS
    SPARSE --> IMS
    VALID --> IMS

    IMS --> UI_TABS["Institutional Memory Workspace\n(Overview, Productivity, Durations, Ledger, Query)"]
    IMS --> EVIDENCE["Evidence Lineage Drawer\n('Where did this number come from?')"]
    IMS --> CSV["RFC 4180 CSV Export Endpoint"]
    IMS --> AGENT_TOOL["Time Agent Tool: query_historical_performance\n(Authoritative Grounding in Chat)"]
```

> [!IMPORTANT]
> **No Vector Database in V1**: Institutional Memory V1 operates entirely on structured relational data in PostgreSQL using deterministic SQL math. There is **no dependency on Qdrant, pgvector, Chroma, or embeddings**. Semantic retrieval of unstructured lessons learned is reserved for V2.

### Implemented V1 Capabilities
1. **Execution Memory Ledger**: Searchable, paginated log of all historical progress increments with discipline, contractor, and date filters.
2. **Executive Summary & Data Quality Audit**: High-level KPIs tracking verified events, total installed quantities by unit, and data quality integrity (e.g., usable ledger entries, records with valid units).
3. **Observed Productivity Rates**: Deterministic calculation of production speed:
   $$\text{Observed Rate} = \frac{\sum \text{installed\_quantity}}{\text{COUNT}(\text{DISTINCT } \text{reporting\_date})}$$
   *Unit Compatibility Invariant*: Incompatible engineering units are strictly isolated. The system never mixes meters, cubic meters, tons, or spools.
4. **Planned vs. Actual Duration Analytics**: Calendar-day duration calculation for completed activities:
   $$\text{Variance Days} = \text{Actual Duration} - \text{Planned Duration}$$
   $$\text{Variance Percent} = \left(\frac{\text{Variance Days}}{\text{Planned Duration}}\right) \times 100$$
5. **Advisory Planning Benchmarks**: Statistical baselines for project disciplines and activity codes:
   * Requires a minimum sample size of **$N \ge 3$** completed activities.
   * Calculates median duration, mean duration, and percentiles (P50, P80 when $N \ge 5$).
   * Explicitly advisory: The system does not autonomously alter planned schedule durations.
6. **Data Quality Status Flags**:
   * `NO_HISTORICAL_BENCHMARK`: Zero historical records found.
   * `INSUFFICIENT_SAMPLE`: Fewer than 3 records available. The observed rate is displayed with a caveat that more history is required.
   * `SUFFICIENT_SAMPLE`: 3 or more verified completed activities available.
7. **Historical Knowledge Query Engine**: Enables structured or natural language questions (e.g., *"What was our historical concrete pouring rate?"*). Queries are resolved against PostgreSQL aggregations, producing deterministic metric values accompanied by grounded explanations.
8. **Evidence Lineage Drawer**: Every metric answers the question: *"Where did this number come from?"* Clicking any metric opens an evidence drawer listing the exact execution events, dates, quantities, source documents, and verbatim excerpts.
9. **RFC 4180 CSV Export**: One-click export of verified historical progress data (`GET /api/v1/projects/{project_id}/institutional-memory/ledger/export`).
10. **Time Agent Tool Integration**: Read-only `query_historical_performance` tool allowing the Time Agent to answer planner questions directly in chat using verified PostgreSQL metrics.

---

## 14. Frontend Workspace Structure

The Next.js 14 single-page workspace (`frontend/app/projects/[id]/page.tsx`) provides 7 project views:

| Tab Identifier | Tab Label | Primary Purpose |
| :--- | :--- | :--- |
| **`overview`** | **Overview** | Executive summary cards (Planned vs Actual Dates, % Complete, Activity Status breakdown). |
| **`wbs`** | **WBS** | Interactive tree view of the Work Breakdown Structure with hierarchical activity rollups. |
| **`activities`** | **Activities** | High-density data grid supporting pagination, multi-column filtering, sorting, and manual activity edits. |
| **`gantt`** | **Gantt** | Interactive CPM timeline visualization rendering activity durations, percent completes, and logic links. |
| **`reports`** | **Field Reports** | Artifact upload interface and the **Lead Planner Review Queue** for approving or reassigning ambiguous events. |
| **`agent`** | **Time Agent** | Conversational execution interface with project-scoped chat history, interactive Action Cards, and proposal staging. |
| **`memory`** | **Institutional Memory** | Dedicated historical intelligence workspace containing 5 specialized subviews. |

### Institutional Memory Subviews (`frontend/components/institutional-memory/`)
* **Overview & Insights (`overview`)**: Summary KPI cards, data quality health audit, top observed production rates, and advisory benchmark cards.
* **Observed Productivity (`productivity`)**: Tabular breakdown of production rates grouped by discipline, contractor, and unit with evidence drawer triggers.
* **Planned vs Actual (`durations`)**: Duration variance table for completed activities with on-time/delayed indicators and P50/P80 metrics.
* **Execution Memory Ledger (`ledger`)**: Filterable, paginated audit table of every historical progress increment with CSV export button.
* **Historical Query (`query`)**: Interactive query runner supporting natural language questions and structured filtering against PostgreSQL.

---

## 15. Verified API Reference

All endpoints are implemented in the current backend (`FastAPI 0.110+` running on port `8080`).

### Projects & Schedule Ingestion
* `GET /projects`: List all projects with activity, WBS, and relationship counts.
* `GET /projects/{project_id}`: Retrieve project details and reference dates.
* `POST /projects/import`: Multipart form upload (`.xer`, `.xml`, `.csv`, `.xlsx`) to parse and persist a new schedule.
* `DELETE /projects/{project_id}`: Cascade delete project and associated schedule/execution entities.

### WBS & Hierarchy
* `GET /projects/{project_id}/wbs`: Flat list of WBS nodes with activity counts.
* `GET /projects/{project_id}/wbs/tree`: Recursive tree structure with parent-child nesting.

### Activities & Relationships
* `GET /projects/{project_id}/activities`: Paginated, filtered activity list (`activity_code`, `status`, `wbs_id`, `sort_by`, `page`, `page_size`).
* `GET /activities/{activity_id}`: Retrieve activity details with linked WBS node.
* `POST /projects/{project_id}/activities`: Manually add an activity.
* `PATCH /activities/{activity_id}`: Update schedule data (`percent_complete`, `status`, `actual_start`, `actual_finish`).
* `DELETE /activities/{activity_id}`: Delete an activity.
* `GET /projects/{project_id}/relationships`: List CPM logic links.
* `POST /projects/{project_id}/relationships`: Create CPM link (`FS`, `SS`, `FF`, `SF` with lag).
* `DELETE /relationships/{relationship_id}`: Remove CPM link.

### Artifacts & Field Ingestion
* `POST /api/v1/projects/{project_id}/artifacts/upload`: Multipart upload of field evidence (PDF, spreadsheet, audio) with SHA-256 deduplication and MinIO storage.
* `GET /api/v1/projects/{project_id}/artifacts`: List stored artifacts for a project.
* `GET /api/v1/artifacts/{artifact_id}`: Get artifact metadata.
* `GET /api/v1/artifacts/{artifact_id}/view-url`: Generate temporary presigned MinIO URL for viewing.
* `GET /api/v1/artifacts/download?key=...`: Direct stream download of artifact binary.
* `POST /api/v1/artifacts/{artifact_id}/extract`: Trigger extraction engine to generate `ExecutionEvents`.

### Matching & Planner Review
* `POST /api/v1/matching/evaluate`: Run multi-signal matching on unmatched execution events.
* `GET /api/v1/review/queue?project_id=...`: Retrieve ambiguous execution events requiring planner review.
* `POST /api/v1/review/decisions`: Submit planner review decision (`APPROVED`, `REASSIGNED`, `REJECTED`).

### Time Agent
* `GET /api/v1/projects/{project_id}/agent/conversations`: List project-scoped conversation summaries (`?q=` search supported).
* `POST /api/v1/projects/{project_id}/agent/conversations`: Start new chat session or get active conversation.
* `GET /api/v1/projects/{project_id}/agent/conversations/{conversation_id}`: Fetch chat history and message metadata.
* `POST /api/v1/projects/{project_id}/agent/conversations/{conversation_id}/messages`: Submit natural language progress report or query.
* `POST /api/v1/projects/{project_id}/agent/conversations/{conversation_id}/attachments`: Attach field report file directly to chat session.
* `POST /api/v1/projects/{project_id}/agent/conversations/{conversation_id}/confirm`: Confirm or reject a staged single-activity update proposal.
* `POST /api/v1/projects/{project_id}/agent/conversations/{conversation_id}/bulk-confirm`: Atomically confirm a staged bulk update proposal.

### Institutional Memory
* `GET /api/v1/projects/{project_id}/institutional-memory/summary`: High-level execution metrics and data quality audit.
* `GET /api/v1/projects/{project_id}/institutional-memory/ledger`: Paginated, filtered historical progress records.
* `GET /api/v1/projects/{project_id}/institutional-memory/productivity`: Observed production rates grouped strictly by compatible units.
* `GET /api/v1/projects/{project_id}/institutional-memory/durations`: Planned vs actual duration variances for completed activities.
* `GET /api/v1/projects/{project_id}/institutional-memory/benchmarks`: Advisory planning benchmark with sample size validation ($N \ge 3$).
* `POST /api/v1/projects/{project_id}/institutional-memory/query`: Execute structured or natural language historical knowledge query.
* `GET /api/v1/projects/{project_id}/institutional-memory/ledger/export`: Export verified historical ledger to RFC 4180 CSV.

### Export & Audit Trail
* `GET /api/v1/projects/{project_id}/audit-trail`: Immutable audit trail showing full lineage to artifacts and MinIO.
* `GET /api/v1/projects/{project_id}/export/xer`: Export updated schedule to native Primavera P6 `.xer` format.

---

## 16. Technology Stack

Verified dependency versions extracted directly from `package.json`, `requirements.txt`, and container definitions:

| Component | Framework / Library | Version | Role in System |
| :--- | :--- | :--- | :--- |
| **Frontend UI** | Next.js (App Router) | `14.2.5` | React web application framework |
| | React | `18.3.1` | Core reactive component library |
| | TypeScript | `5.5.4` | Static type safety |
| | Tailwind CSS | `3.4.7` | Utility-first styling & responsive layouts |
| | Lucide React | `0.428.0` | UI icon set |
| **Backend API** | FastAPI | `≥ 0.110.0` | High-performance asynchronous REST API |
| | SQLAlchemy | `≥ 2.0.28` | Relational ORM & row-level transactional locking |
| | Pydantic | `≥ 2.6.0` | Schema validation and serialization (V2) |
| | Psycopg2-binary | `≥ 2.9.9` | PostgreSQL database adapter |
| | PyPDF | `≥ 4.0.0` | PDF text extraction engine |
| | Openpyxl | `≥ 3.1.0` | Excel spreadsheet parsing |
| **Document Parser** | FastAPI + defusedxml | `≥ 0.110.0` | Secure XML and XER schedule parser service |
| | Pandas | `≥ 2.2.0` | Tabular data manipulation for CSV/XLSX schedules |
| **Storage & DB** | PostgreSQL | `16-alpine` | Primary ACID relational database |
| | MinIO | `RELEASE.2024` | S3-compliant permanent artifact object storage |
| **AI / Models** | Google Gemini API | `2.5-flash` | Time Agent conversational intent & clarification |
| | Google Gemini API | `3.5-flash` | Artifact document & tabular extraction |

---

## 17. Docker & Local Development Setup

### Prerequisites
* **Docker** (v24.0+) & **Docker Compose** (v2.20+)
* **Git**
* *(Optional for native development)*: Python 3.12+, Node.js 18+, PostgreSQL 16 client

### Quick Start (Docker Compose)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/BatraKrishal/ScheduleManager.git
   cd ScheduleManager
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and provide your Google Gemini API credentials (see [Environment Variables](#18-environment-variables)).

3. **Build and launch all services**:
   ```bash
   docker compose up --build -d
   ```

4. **Verify container health**:
   ```bash
   docker compose ps
   ```

### Application URLs
* **Web UI Dashboard**: [http://localhost:3000](http://localhost:3000)
* **Backend REST API Docs**: [http://localhost:8080/docs](http://localhost:8080/docs)
* **Document Parser API Docs**: [http://localhost:8001/docs](http://localhost:8001/docs)
* **MinIO Object Console**: [http://localhost:9001](http://localhost:9001) *(User: `minioadmin` / Pass: `minioadmin`)*

---

## 18. Environment Variables

ScheduleManager isolates LLM credentials and configuration per service. Configure these variables in your root `.env` file:

```bash
# ==============================================================================
# Database Configuration
# ==============================================================================
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=primavera
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/primavera

# ==============================================================================
# Service Ports & Networking
# ==============================================================================
BACKEND_PORT=8080
PARSER_URL=http://document-parser:8001
NEXT_PUBLIC_API_URL=http://localhost:8080

# ==============================================================================
# MinIO S3 Object Storage
# ==============================================================================
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET=sih-artifacts
MINIO_SECURE=false

# ==============================================================================
# Primary LLM Credentials (Isolated per Service)
# ==============================================================================
# Time Agent Conversational Model
TIME_AGENT_GEMINI_API_KEY=your_gemini_api_key_here
TIME_AGENT_LLM_MODEL=gemini-2.5-flash

# Document & Artifact Extraction Model
EXTRACTION_GEMINI_API_KEY=your_gemini_api_key_here
EXTRACTION_LLM_MODEL=gemini-3.5-flash

# ==============================================================================
# Backward-Compatibility Fallback (Development Only)
# ==============================================================================
# If specific keys are omitted, the backend can fall back to GEMINI_API_KEY in dev
ALLOW_LEGACY_GEMINI_FALLBACK=true
GEMINI_API_KEY=your_fallback_gemini_api_key
```

*Security Note: Never commit production API keys or `.env` files to source control.*

---

## 19. Automated Test Suite

The test suite provides thorough verification across import roundtrips, extraction, matching algorithms, Time Agent intent handling, bulk proposals, and Institutional Memory analytics.

### Running Backend Tests
Execute pytest directly inside the running backend container:
```bash
docker exec primavera-backend pytest tests/ -v
```

**Verified Test Results (65 Passed)**:
```text
============================== test session starts ==============================
platform linux -- Python 3.12.14, pytest-8.4.2, pluggy-1.6.0
rootdir: /app
plugins: anyio-4.15.1
collected 65 items

tests/test_activities_api.py::test_list_activities_pagination PASSED
tests/test_activities_api.py::test_update_activity_patch PASSED
tests/test_activities_api.py::test_activity_bounds_validation PASSED
tests/test_activities_api.py::test_delete_activity PASSED
tests/test_relationships_api.py::test_create_relationship_success PASSED
tests/test_relationships_api.py::test_prevent_duplicate_relationship PASSED
tests/test_relationships_api.py::test_prevent_self_relationship PASSED
tests/test_validation.py::test_valid_activity_payload PASSED
tests/test_validation.py::test_negative_duration_fails PASSED
tests/test_validation.py::test_invalid_percent_fails PASSED
tests/test_validation.py::test_finish_before_start_fails PASSED
tests/test_validation.py::test_invalid_status_enum PASSED
tests/test_import_e2e.py::test_import_xer_full_schedule PASSED
tests/test_import_e2e.py::test_import_invalid_file_type PASSED
tests/test_xer_export_roundtrip.py::test_xer_export_endpoint_returns_valid_p6_file PASSED
tests/test_xer_export_roundtrip.py::test_xer_export_contains_updated_progress PASSED
tests/test_credential_resolver.py::test_time_agent_dedicated_credentials PASSED
... (9 tests for credential isolation & fallbacks) ...
tests/test_extraction_matching_integration.py::test_artifact_upload_and_minio_storage PASSED
tests/test_extraction_matching_integration.py::test_artifact_duplicate_detection PASSED
tests/test_extraction_matching_integration.py::test_extraction_creates_structured_events_with_provenance PASSED
tests/test_extraction_matching_integration.py::test_matching_confidence_routing_high_and_auto_link PASSED
tests/test_extraction_matching_integration.py::test_matching_low_confidence_routes_to_planner_review PASSED
tests/test_extraction_matching_integration.py::test_planner_review_approval_and_schedule_update PASSED
tests/test_extraction_matching_integration.py::test_full_pipeline_audit_trail_and_p6_export PASSED
tests/test_time_agent.py::test_conversational_parser_date_resolution PASSED
tests/test_time_agent.py::test_incremental_and_cumulative_quantity_semantics PASSED
tests/test_time_agent.py::test_proposal_lifecycle_and_conflict_handling PASSED
tests/test_time_agent.py::test_conversational_clarification_and_confirmation_flow PASSED
tests/test_time_agent.py::test_bulk_intent_recognition_and_proposal_card PASSED
tests/test_time_agent.py::test_bulk_proposal_confirmation_executes_atomic_schedule_mutation PASSED
tests/test_time_agent.py::test_project_scoped_chat_isolation PASSED
tests/test_institutional_memory.py::test_empty_ledger_summary_and_quality_audit PASSED
tests/test_institutional_memory.py::test_ledger_pagination_and_discipline_filtering PASSED
tests/test_institutional_memory.py::test_observed_productivity_calculation PASSED
tests/test_institutional_memory.py::test_unit_isolation_in_productivity PASSED
tests/test_institutional_memory.py::test_duration_variance_calculation PASSED
tests/test_institutional_memory.py::test_planning_benchmark_sample_size_rules PASSED
tests/test_institutional_memory.py::test_institutional_memory_query_service PASSED
tests/test_institutional_memory.py::test_ledger_csv_export PASSED
tests/test_institutional_memory.py::test_time_agent_historical_query_tool PASSED
tests/test_institutional_memory.py::test_api_endpoints_via_client PASSED

====================== 65 passed in 23.14s ======================
```

### Running Document Parser Tests
```bash
docker exec primavera-document-parser pytest tests/ -v
```
**Verified Result**: `9 passed in 2.14s` (testing XER, XML, CSV, XLSX, and malformed schedule handlers).

---

## 20. End-to-End Demo Walkthrough

This scenario demonstrates the end-to-end flow using the seeded `BOROUGE4_DEMO` schedule:

### Step 1: Open Project Workspace
1. Navigate to [http://localhost:3000](http://localhost:3000).
2. Click into **`BOROUGE4_DEMO`** (`d2c363c7-dbe1-4bab-95e2-c96ca02da053`).
3. View the 64 schedule activities organized under Civil, Structural, Mechanical, Electrical, and Piping WBS nodes.

### Step 2: Report Progress via Time Agent
1. Click the **Time Agent** tab.
2. In the chat input, type:
   ```text
   We poured 35 m3 concrete today for foundation F-204
   ```
3. The Time Agent invokes `ConversationalParser`:
   * Identifies intent: `PROGRESS_REPORT`
   * Extracts: `quantity: 35.0`, `unit: "m3"`, `location: "F-204"`, `discipline: "Civil"`
4. `MatchingService` retrieves candidates and finds `CIV-1004` and `CIV-1005` (Foundation Pours F-204 & F-205).
5. Because scores are close, the agent returns an interactive clarification card:
   > *"Did this work apply to CIV-1004 (Foundation Pour F-204) or CIV-1005 (Foundation Pour F-205)?"*

### Step 3: Clarification & Staging
1. Click `[CIV-1004 - Foundation Pour F-204]`.
2. The agent stages an `UpdateProposal` and presents a **Proposal Confirmation Card**:
   * Activity: `CIV-1004` (Foundation Pour F-204)
   * Current Progress: `0%` $\rightarrow$ Proposed: `14%` (`+35 m3`)
   * Execution Date: `2024-01-01`
3. Click **"Confirm Update"**.

### Step 4: Governed Mutation & Audit Verification
1. `ScheduleUpdateService` executes an atomic row-locked transaction:
   * Sets `CIV-1004` status to `IN_PROGRESS`, percent to `14%`.
   * Inserts an append-only row in `actual_progress_ledger`.
   * Records a full state snapshot in `schedule_audit_log`.
2. Navigate to the **Activities** tab: Confirm `CIV-1004` now reflects `14%` complete.
3. Navigate to the **Gantt** tab: Confirm progress bar shading on `CIV-1004`.

### Step 5: Governed Bulk Update Demo
1. In the Time Agent, type:
   ```text
   We completed all the electrical activities
   ```
2. The agent queries PostgreSQL and detects 4 matching activities (`ELE-1001` through `ELE-1004`).
3. The agent renders a **Bulk Scope Proposal Card** listing all 4 activities.
4. Click **"Update All 4 to 100%"**.
5. All 4 activities transition atomically to `COMPLETED` (`100%`), generating 4 ledger records and 4 audit entries.

### Step 6: Institutional Memory Inspection
1. Click the **Institutional Memory** tab.
2. **Overview Subtab**:
   * Inspect the updated KPI cards (Usable Ledger Entries, Total Installed Quantities).
   * Review the **Data Quality Audit** confirming valid records.
3. **Observed Productivity Subtab**:
   * View the Civil concrete pouring rate: `35.0 m3/reporting-day`.
   * Click **"Evidence"**: An Evidence Drawer slides out displaying the exact execution event, timestamp, and verbatim report snippet.
4. **Historical Query Subtab**:
   * Type: *"What was our historical concrete pouring rate?"*
   * The query engine returns the exact PostgreSQL metric (`35.0 m3/day`) with sample size and grounded commentary.
5. Click **"Export CSV"** to download the verified ledger.

---

## 21. Current Feature Matrix

| Functional Capability | Current Status | Implementation Mechanism |
| :--- | :--- | :--- |
| **Primavera P6 XER Ingestion** | **Implemented** | Tabular `%T` block parser in `document-parser` microservice. |
| **Primavera P6 XML Ingestion** | **Implemented** | Hierarchical XML schema parser in `document-parser`. |
| **CSV / XLSX Schedule Ingestion** | **Implemented** | Normalized column mapping via pandas & openpyxl. |
| **Canonical Schedule Normalization** | **Implemented** | Relational persistence into `projects`, `wbs`, `activities`, `activity_relationships`. |
| **Primavera P6 XER Export** | **Implemented** | Roundtrip generator (`/export/xer`) reflecting verified actuals. |
| **Deterministic Multi-Signal Matching** | **Implemented** | 5 weighted signals ($S_{id}, S_{text}, S_{wbs}, S_{temp}, S_{context}$) in `MatchingService`. |
| **Confidence Routing Policy** | **Implemented** | `AUTO_LINK` ($\ge 0.85$, $\Delta \ge 0.15$), `PLANNER_REVIEW` ($\ge 0.50$), `UNMATCHED`. |
| **Lead Planner Review Queue** | **Implemented** | Full UI queue with presigned MinIO evidence preview, approval, rejection, and reassignment. |
| **Time Agent Conversational Interface** | **Implemented** | Project-scoped chat with Gemini 2.5 Flash intent parsing. |
| **Project-Scoped Chat Isolation** | **Implemented** | Multi-chat session manager; no cross-project conversation leakage. |
| **Dynamic Multi-Choice Clarification** | **Implemented** | Pairwise A/B options, structured candidate lists (up to 4), and `None of these`. |
| **Governed Bulk Progress Intent** | **Implemented** | PostgreSQL authoritative scope resolution with multi-activity preview cards. |
| **CPM Protection Firewall** | **Implemented** | Baseline dates (`planned_start`/`finish`) protected against execution overwrites. |
| **Incremental & Cumulative Semantics** | **Implemented** | Monotonicity checks and mathematical ratio derivation in `ScheduleUpdateService`. |
| **Append-Only Actual Progress Ledger** | **Implemented** | Relational `actual_progress_ledger` capturing every verified quantity increment. |
| **End-to-End Audit Trail** | **Implemented** | `schedule_audit_log` with JSON previous/new state diffs and MinIO storage keys. |
| **Institutional Memory Engine V1** | **Implemented** | Deterministic PostgreSQL analytics (observed productivity, duration variances, benchmarks). |
| **Evidence Lineage Drawer** | **Implemented** | Interactive UI drawer tracing historical metrics to source execution events. |
| **Historical CSV Export** | **Implemented** | RFC 4180 CSV export endpoint (`/institutional-memory/ledger/export`). |
| **Time Agent Historical Query Tool** | **Implemented** | Read-only tool grounding agent answers in verified PostgreSQL metrics. |
| **Semantic / Vector Memory (pgvector/Qdrant)** | *Future / V2* | Deferred. V1 uses pure structured PostgreSQL data. |
| **Live Speech-to-Text Transcription** | *Future / V2* | Deferred. Audio files are stored permanently in MinIO as evidence. |
| **Enterprise OAuth2 / OIDC / JWT Hardening** | *Future / V2* | Prototype uses trusted caller identity (`X-User-ID` header). |
| **Autonomous CPM Rescheduling** | *Not Supported* | Architecture maintains planner authority; does not automatically re-level or reschedule CPM. |

---

## 22. V1 Limitations & Engineering Non-Claims

To ensure transparent evaluation, ScheduleManager explicitly identifies its architectural boundaries:

1. **No Semantic / Vector Memory in V1**: V1 Institutional Memory is strictly backed by structured PostgreSQL tables and deterministic SQL queries. There is no vector database (no Qdrant, Chroma, or pgvector).
2. **Audio Storage vs Transcription**: Voice memos are securely stored in MinIO and registered in PostgreSQL as evidence. Automatic speech-to-text transcription is not yet integrated.
3. **Authentication Scope**: The V1 prototype uses trusted caller headers (`X-User-ID: site-supervisor`) for user attribution and audit logging. Enterprise OAuth2, OIDC, and JWT role-based access control are deferred.
4. **Project-Scoped Benchmarks**: V1 Institutional Memory operates within the scope of the active project. Cross-project organizational benchmarking across disparate project databases is planned for V1.1.
5. **No Structured Delay Root-Cause Taxonomy**: While the system tracks duration variances and records whether an activity finished delayed, it does not infer root causes (e.g., weather, permitting, engineering holds) without explicit taxonomy tagging.
6. **No Autonomous CPM Rescheduling**: The platform deliberately refrains from autonomously re-leveling resources or altering planned CPM network logic. The planner retains final authority over schedule baseline revisions.

---

## 23. Product Roadmap

### Version 1.1 (Near-Term Hardening)
* **Cross-Project Benchmarking**: Aggregating verified productivity rates across multiple project databases within an enterprise account.
* **Structured Delay Taxonomy**: Standardized delay-reason tagging (e.g., Owner Change, Weather, Late Submittal) linked to `ReviewDecision`.
* **Lead Planner Calibration Tools**: Granular calibration sliders for matching signal weights.
* **Enterprise Authentication**: Production OAuth2 / OIDC authentication with role-based permissions (Viewer, Supervisor, Lead Planner, Admin).
* **Automated Audio Transcription**: Speech-to-text worker processing MinIO voice memos into draft `ExecutionEvents`.

### Version 2.0 (Advanced Intelligence)
* **Hybrid Semantic Memory**: Integration of `pgvector` for semantic retrieval of qualitative lessons learned, incident reports, and site photos.
* **CPM Schedule Impact Advisory**: Predictive lookahead analyzing critical path float erosion based on observed historical production rates.
* **Bi-Directional PMIS Integration**: Connectors for Autodesk Construction Cloud (ACC), Procore, and Oracle Primavera Cloud (OPC).

---

## 24. Repository Structure

```text
ScheduleManager/
├── backend/                                # Core FastAPI backend service
│   ├── app/
│   │   ├── api/                            # REST API route controllers
│   │   │   ├── activities.py               # Activity CRUD & filtering
│   │   │   ├── agent.py                    # Time Agent endpoints
│   │   │   ├── analytics.py                # Institutional Memory endpoints
│   │   │   ├── artifacts.py                # Artifact upload & extraction
│   │   │   ├── export.py                   # P6 XER export & audit trail
│   │   │   ├── matching.py                 # Multi-signal matching evaluation
│   │   │   ├── projects.py                 # Project management & ingestion
│   │   │   ├── relationships.py            # Precedence link management
│   │   │   ├── review.py                   # Lead Planner review queue
│   │   │   └── wbs.py                      # WBS tree endpoints
│   │   ├── domain/                         # Domain models & database configuration
│   │   │   ├── database.py                 # SQLAlchemy engine & session factory
│   │   │   └── models.py                   # 13 authoritative SQLAlchemy entities
│   │   ├── repositories/                   # Data access layer
│   │   ├── schemas/                        # Pydantic validation schemas
│   │   │   ├── agent.py                    # Time Agent DTOs & Action Cards
│   │   │   ├── artifact.py                 # Artifact DTOs
│   │   │   ├── extraction.py               # ExecutionEvent schemas
│   │   │   ├── institutional_memory.py     # Institutional Memory DTOs
│   │   │   ├── matching.py                 # Candidate & routing DTOs
│   │   │   └── review.py                   # Planner review schemas
│   │   └── services/                       # Business logic service layer
│   │       ├── agent_parser.py             # Gemini conversational parser
│   │       ├── agent_service.py            # Time Agent lifecycle coordinator
│   │       ├── credential_resolver.py      # LLM key isolation & fallbacks
│   │       ├── extraction_service.py       # Document extraction engine
│   │       ├── historical_analytics_service.py # Pure SQL analytics engine
│   │       ├── institutional_memory_service.py # Memory queries & CSV export
│   │       ├── matching_service.py         # 5-signal deterministic matcher
│   │       ├── minio_service.py            # MinIO S3 client wrapper
│   │       ├── schedule_update_service.py  # Governed schedule mutation
│   │       └── validation_service.py       # Domain invariant validator
│   ├── tests/                              # Comprehensive backend test suite (65 tests)
│   ├── Dockerfile                          # Backend container definition
│   └── requirements.txt                    # Python dependencies
├── document-parser/                        # Schedule parser microservice (Port 8001)
│   ├── app/
│   │   ├── parsers/                        # Specialized schedule file parsers
│   │   │   ├── csv_parser.py               # CSV schedule parser
│   │   │   ├── xer_parser.py               # Primavera P6 XER parser
│   │   │   ├── xlsx_parser.py              # Excel schedule parser
│   │   │   └── xml_parser.py               # Primavera P6 XML parser
│   │   └── main.py                         # Parser microservice API
│   ├── tests/                              # Parser test suite (9 tests)
│   ├── Dockerfile                          # Parser container definition
│   └── requirements.txt                    # Parser dependencies
├── frontend/                               # Next.js 14 web application
│   ├── app/                                # App Router pages
│   │   ├── projects/[id]/page.tsx          # Main project workspace (7 tabs)
│   │   ├── layout.tsx                      # Root layout
│   │   └── page.tsx                        # Projects overview dashboard
│   ├── components/                         # React UI components
│   │   ├── institutional-memory/           # Institutional Memory components
│   │   │   ├── BenchmarkAdvisoryCard.tsx   # Advisory benchmark banner
│   │   │   ├── DurationVarianceTable.tsx   # Planned vs actual table
│   │   │   ├── EvidenceDrawer.tsx          # Provenance slide-out drawer
│   │   │   ├── ExecutionMemoryLedger.tsx   # Filterable historical ledger
│   │   │   ├── HistoricalQueryPanel.tsx    # Natural language query runner
│   │   │   ├── InstitutionalMemoryWorkspace.tsx # Memory tab root
│   │   │   ├── ProductivityTable.tsx       # Observed production rates
│   │   │   └── SummaryCards.tsx            # Data quality KPI cards
│   │   ├── ActivityTable.tsx               # High-density activity grid
│   │   ├── FieldReportsAndReview.tsx       # Planner review queue
│   │   ├── GanttChart.tsx                  # Interactive CPM timeline
│   │   ├── TimeAgentChat.tsx               # Time Agent conversational UI
│   │   └── WbsTree.tsx                     # Hierarchical WBS tree
│   ├── lib/                                # API client & TypeScript types
│   ├── package.json                        # Frontend dependencies & scripts
│   └── tailwind.config.ts                  # Tailwind design system tokens
├── samples/                                # Sample schedule files
│   ├── sample.xer                          # P6 XER reference schedule (64 activities)
│   ├── sample.xml                          # P6 XML reference schedule
│   ├── sample.csv                          # CSV schedule
│   └── sample.xlsx                         # Excel schedule
├── docs/                                   # In-depth architectural specifications
│   ├── EXTRACTION_MATCHING_SCHEDULE_INTEGRATION.md # 33-section integration specification
│   ├── INTEGRATION_SOURCE_GROUNDING_AUDIT.md       # Integration source audit
│   └── PPT_HANDOFF.md                              # Presentation handoff documentation
├── docker-compose.yml                      # Full multi-container stack orchestration
├── .env.example                            # Environment variable template
└── README.md                               # Authoritative technical documentation
```

---

## 25. Engineering Grounding & Invariant Commitments

ScheduleManager is designed around engineering invariants rather than probabilistic assumptions:

* **PostgreSQL is the single source of truth**: Schedules, execution events, ledgers, and audit logs reside in relational storage under ACID guarantees.
* **The LLM does not execute mutations**: Natural language is interpreted into structured proposals; human confirmation is mandatory.
* **Deterministic formulas govern progress and analytics**: Production rates, duration variances, and match scores are computed using explicit mathematical formulas, not generative guesses.
* **Complete provenance is preserved**: Every historical metric and schedule update can be traced back to an exact execution event, artifact hash, and MinIO storage key.
* **Sparse data is flagged honestly**: When insufficient execution history exists, the system reports `INSUFFICIENT_SAMPLE` rather than manufacturing synthetic benchmarks.