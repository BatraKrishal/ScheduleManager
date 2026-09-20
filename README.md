# Primavera Schedule Platform (P0)

A production-grade Primavera schedule management web platform supporting import, normalization, relational persistence, querying, spreadsheet editing, and Gantt timeline visualization for Oracle Primavera schedules.

## Architecture

```
                        ┌───────────────────────────┐
                        │   Frontend (Next.js 14)   │
                        │   TypeScript + Tailwind   │
                        │   Port 3000               │
                        └─────────────┬─────────────┘
                                      │ HTTP / JSON
                                      ▼
                        ┌───────────────────────────┐
                        │     Backend Service       │
                        │     FastAPI + SQLAlchemy  │
                        │     Port 8000             │
                        └──────┬─────────────┬──────┘
                               │             │
                  HTTP Multipart/Form        │ SQL (PostgreSQL Driver)
                               │             │
                               ▼             ▼
┌──────────────────────────────────┐   ┌───────────────────────────┐
│     Document Parser Service      │   │    PostgreSQL Database    │
│     FastAPI + Pydantic           │   │    Relational Schema      │
│     XER, XML, CSV, XLSX Parsers  │   │    Port 5432              │
│     Port 8001                    │   └───────────────────────────┘
└──────────────────────────────────┘
```

### Services

| Service | Port | Technology | Purpose |
| :--- | :--- | :--- | :--- |
| **`frontend`** | `3000` | Next.js 14, TypeScript, Tailwind CSS | Schedule dashboard, spreadsheet activity editor, WBS hierarchy tree, interactive Gantt chart |
| **`backend`** | `8080` (or `${BACKEND_PORT}`) | FastAPI, SQLAlchemy 2.0, PostgreSQL | Business validation, relational persistence, schedule querying, activity CRUD & PATCH updates |
| **`document-parser`** | `8001` | FastAPI, Pydantic, openpyxl, defusedxml | Independent parsing service normalizing `.xer`, `.xml`, `.csv`, and `.xlsx` into canonical JSON |
| **`postgres`** | `5432` | PostgreSQL 16 Alpine | Relational database (source of truth for schedules) |

---

## System Integration Specification

* [EXTRACTION_MATCHING_SCHEDULE_INTEGRATION.md](file:///c:/Users/Gues/Desktop/sihnew/ScheduleManager/EXTRACTION_MATCHING_SCHEDULE_INTEGRATION.md): Complete, standalone 33-section engineering implementation specification detailing the Field Report Ingestion → Extraction Engine → Normalization → Candidate Retrieval → Activity Matching → Confidence Routing → Human Review → Schedule Update Generation → Safe Writeback to Primavera P6 & Microsoft Project.

---

## Supported Schedule Formats

1. **Primavera P6 `.xer`**: Tabular relational export parsing `%T`, `%F`, `%R`, `%E` blocks across `PROJECT`, `PROJWBS`, `TASK`, and `TASKPRED` tables.
2. **Primavera P6 `.xml`**: Hierarchical XML export schema parsing `<Project>`, `<WBS>`, `<Activity>`, and `<Relationship>` elements with namespace resolution.
3. **Primavera `.csv`**: Header-aware CSV mapping standard P6 columns (`Activity ID`, `Activity Name`, `WBS`, `Status`, `Start`, `Finish`, `Duration`, `% Complete`, `Predecessors`).
4. **Excel `.xlsx`**: Multi-sheet workbook parser supporting the same column aliases as CSV.

---

## Quick Start (Docker Compose)

### 1. Launch All Services

```bash
docker compose up --build
```

The database tables are automatically initialized on backend startup.

### 2. Open the Application

* **Web UI Dashboard**: [http://localhost:3000](http://localhost:3000)
* **Backend API Docs**: [http://localhost:8080/docs](http://localhost:8080/docs)
* **Document Parser API Docs**: [http://localhost:8001/docs](http://localhost:8001/docs)

---

## Sample Files Provided

Located in [`samples/`](file:///c:/Users/LOQ/OneDrive/Desktop/sih/samples/):

* `samples/sample.xer`: Valid Primavera P6 XER file with 64 activities, WBS, and CPM logic links.
* `samples/sample.xml`: Valid Primavera P6 XML format.
* `samples/sample.csv`: Valid CSV export with predecessor link notation.
* `samples/sample.xlsx`: Valid Excel workbook schedule.
* `samples/invalid_dates.csv`: Negative test case (finish date precedes start date).
* `samples/missing_wbs.xml`: Negative test case (orphan activity referencing non-existent WBS).

---

## Canonical Schedule Representation

The document parser converts all input formats into this canonical JSON model:

```json
{
  "project": {
    "project_code": "BOROUGE4_DEMO",
    "name": "BOROUGE4_DEMO",
    "planned_start": "2024-01-01T08:00:00",
    "planned_finish": "2025-12-31T17:00:00",
    "data_date": "2024-01-01T08:00:00"
  },
  "wbs": [
    {
      "code": "WBS.1",
      "name": "Civil Works",
      "parent_code": null
    }
  ],
  "activities": [
    {
      "activity_code": "CIV-1001",
      "name": "Site Clearing",
      "wbs_code": "WBS.1",
      "activity_type": "TT_Task",
      "status": "COMPLETED",
      "planned_start": "2024-01-01T08:00:00",
      "planned_finish": "2024-01-15T17:00:00",
      "actual_start": "2024-01-01T08:00:00",
      "actual_finish": "2024-01-15T17:00:00",
      "original_duration": 10.0,
      "remaining_duration": 0.0,
      "percent_complete": 100.0,
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

---

## API Endpoints

### Projects
* `GET /projects`: List all imported projects with activity, WBS, and relationship counts.
* `GET /projects/{id}`: Get project details.
* `POST /projects/import`: Multipart form file upload (`.xer`, `.xml`, `.csv`, `.xlsx`).
* `DELETE /projects/{id}`: Delete project and cascade associated WBS, activities, and relationships.

### WBS
* `GET /projects/{id}/wbs`: Flat list of WBS elements with activity counts.
* `GET /projects/{id}/wbs/tree`: Recursive tree structure with children and activity counts.

### Activities
* `GET /projects/{id}/activities`: Paginated, sorted, and filtered activities list.
  * Query parameters: `activity_code`, `name`, `wbs_id`, `status`, `start_date_from`, `start_date_to`, `percent_min`, `percent_max`, `sort_by`, `sort_dir`, `page`, `page_size`.
* `GET /activities/{id}`: Get activity details with linked WBS node.
* `POST /projects/{id}/activities`: Manually add an activity.
* `PATCH /activities/{id}`: Update schedule data (name, status, planned/actual dates, duration, % complete, WBS).
* `DELETE /activities/{id}`: Delete an activity.

### Relationships
* `GET /projects/{id}/relationships`: List logic relationships with activity names.
* `POST /projects/{id}/relationships`: Add a relationship (`FS`, `SS`, `FF`, `SF` with lag).
* `PATCH /relationships/{id}`: Update relationship type or lag.
* `DELETE /relationships/{id}`: Delete a relationship.

---

## Running Automated Tests

### 1. Document Parser Unit Tests
```bash
cd document-parser
python -m pytest tests
```
* Tests valid parsing for `.xer`, `.xml`, `.csv`, and `.xlsx`.
* Tests error handling for empty files, corrupt XML, missing required columns, and unsupported extensions.

### 2. Backend Unit and Integration Tests
```bash
cd backend
python -m pytest tests
```
* Tests project import workflow and transactional database persistence.
* Tests activity query filtering, sorting, and pagination.
* Tests activity PATCH updates and percent complete bounds validation.
* Tests relationship logic (self-reference prevention, duplicate prevention).