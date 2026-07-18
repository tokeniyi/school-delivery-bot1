# Architecture Reference — SchoolRelay Bot

> **Primary reference:** This document is the authoritative architectural guide for the SchoolRelay Telegram delivery-matching bot. It must be kept in sync with the implementation at all times (see [INSTRUCTIONS.md](../INSTRUCTIONS.md)).

---

## System Overview

### Purpose

SchoolRelay is a Telegram bot that matches students who need packages delivered to school with parents who are already making that trip. An admin reviews and approves or rejects every proposed match before notifications are sent to both parties.

### High-Level Architecture

The system follows a strict four-layer architecture:

```
Interface Layer      (bot/handlers/)
        ↓
Application Layer    (services/)
        ↓
Domain Layer         (database/enums.py, business rules)
        ↓
Infrastructure Layer (database/crud.py, database/db.py, bot/client.py)
```

Each layer may only depend on the layer directly below it. Skipping layers is a violation of the Dependency Rules in [INSTRUCTIONS.md](../INSTRUCTIONS.md).

### Dependency Flow

```
bot/handlers/
    start.py        → UserService
    student.py      → UserService, StudentRequestService, MatchingService
    parent.py       → UserService, ParentTravelService, MatchingService
    admin.py        → MatchingService, HealthCheckService

services/
    user_service.py         → database.crud
    request_service.py      → database.crud
    travel_service.py       → database.crud
    matching_service.py     → services.matching, database.crud, services.notifications
    health_service.py       → database.db, bot.client
    matching.py             → database.db, database.models
    notifications.py        → bot.client, database.db, database.models

database/
    crud.py     → database.models, database.enums
    db.py       → config
    models.py   → (SQLAlchemy Base)
    enums.py    → (stdlib only)
```

### Data Flow — Student Request Submission

```
User types delivery details
        ↓
student.py FSM handlers (validate input at Interface Layer)
        ↓
StudentRequestService.register_request()
        ↓
database.crud.create_student_request()  →  DB: StudentRequest row
        ↓
MatchingService.trigger_automatic_matching()
        ↓
services.matching.find_matches()        →  DB: JOIN query
        ↓
database.crud.create_match()            →  DB: Match row
        ↓
services.notifications.notify_admin_match()  →  Telegram API
```

### Data Flow — Match Approval

```
Admin taps "Approve" inline button
        ↓
admin.py callback_approve_match()
        ↓
MatchingService.approve_match()
        ↓
database.crud.approve_match()           →  DB: Match / Request / Travel / AuditLog
        ↓
notifications.notify_student_approved()
notifications.notify_parent_approved()  →  Telegram API
```

---

## Module Overview

### Interface Layer — `bot/handlers/`

| File | Purpose | Responsibilities |
|------|---------|-----------------|
| `start.py` | `/start` command | Receive Telegram update, call UserService, send welcome reply |
| `student.py` | Student FSM flow | Collect & validate request fields, call StudentRequestService + MatchingService |
| `parent.py` | Parent FSM flow | Collect & validate travel fields, call ParentTravelService + MatchingService |
| `admin.py` | Admin commands & callbacks | Auth check, call MatchingService / HealthCheckService, send reply |

**Allowed:** Receive input, send responses, auth guard, FSM transitions.  
**Forbidden:** Business logic, persistence calls, external service orchestration.

---

### Application Layer — `services/`

| File | Class | Purpose |
|------|-------|---------|
| `user_service.py` | `UserService` | User registration and role management |
| `request_service.py` | `StudentRequestService` | Student delivery-request registration |
| `travel_service.py` | `ParentTravelService` | Parent travel-schedule registration |
| `matching_service.py` | `MatchingService` | Automatic matching loop, approve/reject workflows |
| `health_service.py` | `HealthCheckService` | DB and Telegram API connectivity probes |
| `matching.py` | `find_matches()` | Optimised SQL-JOIN match-discovery query |
| `notifications.py` | helpers | Telegram notification delivery with retry |

**Allowed:** Feature orchestration, use-case coordination, calling infrastructure.  
**Forbidden:** Raw SQLAlchemy queries, framework-specific persistence, direct `async_session` usage inside handlers.

#### `UserService`
- **`register_or_update_user(telegram_id, username, full_name)`** — Insert new user or update name fields.
- **`set_user_role(telegram_id, role)`** — Assign student/parent role.
- **Dependencies:** `database.crud.create_user`, `database.crud.update_user_role`

#### `StudentRequestService`
- **`register_request(...)`** — Persist a delivery request (upserts pending request).
- **Dependencies:** `database.crud.create_student_request`

#### `ParentTravelService`
- **`register_travel(...)`** — Persist a travel availability (upserts available travel).
- **Dependencies:** `database.crud.create_parent_travel`

#### `MatchingService`
- **`trigger_automatic_matching()`** — Run `find_matches()`, persist new Match rows, notify admins.
- **`get_pending_matches()`** — Return all pending-review matches with eager-loaded relationships.
- **`approve_match(match_id, admin_id)`** — Approve match, update statuses, send notifications.
- **`reject_match(match_id, admin_id)`** — Reject match, reset statuses, send notifications.
- **Dependencies:** `services.matching`, `database.crud`, `services.notifications`

#### `HealthCheckService`
- **`check_database()`** → `HealthStatus` — Probe DB with `SELECT 1`.
- **`check_telegram()`** → `HealthStatus` — Probe Telegram API with `getMe`.
- **Dependencies:** `database.db`, `bot.client`

---

### Domain Layer — `database/enums.py`

Business rules encoded as enumerations:

| Enum | Values | Meaning |
|------|--------|---------|
| `RequestStatus` | `PENDING`, `MATCHED` | Lifecycle of a student request |
| `TravelStatus` | `AVAILABLE`, `MATCHED`, `UNAVAILABLE` | Lifecycle of a parent travel |
| `MatchStatus` | `PENDING_REVIEW`, `APPROVED`, `REJECTED` | Admin review state of a match |

Business rule: A match may only be approved or rejected when its status is `PENDING_REVIEW`.  
Business rule: Rejecting a match resets the request to `PENDING` and the travel to `AVAILABLE`, enabling re-matching.

---

### Infrastructure Layer — `database/`

| File | Purpose |
|------|---------|
| `db.py` | SQLAlchemy async engine + session factory |
| `models.py` | ORM models: `User`, `StudentRequest`, `ParentTravel`, `Match`, `AuditLog` |
| `crud.py` | All database read/write operations |

**Cascade rules:** Deleting a `User` cascades to their `StudentRequest` and `ParentTravel` rows.  
**Race-condition safety:** `create_match` performs a within-transaction duplicate check before insert.  
**Audit trail:** Every admin approve/reject writes a timestamped `AuditLog` row.

---

### Infrastructure Layer — `bot/client.py`

Provides a single, shared `Bot` instance to prevent Telegram session collisions across modules.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│              INTERFACE LAYER                    │
│  start.py  student.py  parent.py  admin.py      │
└──────────────────┬──────────────────────────────┘
                   │ calls
┌──────────────────▼──────────────────────────────┐
│             APPLICATION LAYER                   │
│  UserService  StudentRequestService             │
│  ParentTravelService  MatchingService           │
│  HealthCheckService                             │
│  ─────────────────────────────────────────────  │
│  matching.py (find_matches)                     │
│  notifications.py (notify_*)                    │
└──────────────────┬──────────────────────────────┘
                   │ calls
┌──────────────────▼──────────────────────────────┐
│               DOMAIN LAYER                      │
│  enums.py: RequestStatus, TravelStatus,         │
│            MatchStatus                          │
└──────────────────┬──────────────────────────────┘
                   │ uses
┌──────────────────▼──────────────────────────────┐
│           INFRASTRUCTURE LAYER                  │
│  database/crud.py  database/db.py               │
│  database/models.py  bot/client.py              │
│  config.py  Redis  External Telegram API        │
└─────────────────────────────────────────────────┘
```

---

## Feature Ownership Map

### User Registration

| Property | Value |
|----------|-------|
| **Owner** | `UserService` |
| **Entry Points** | `/start` Telegram command |
| **Dependencies** | `database.crud.create_user`, `database.crud.update_user_role` |
| **Business Rules** | Upsert: update existing user on re-registration; default role is `Student` |
| **Persistence** | `User` table |
| **External** | None |

---

### Student Delivery Request

| Property | Value |
|----------|-------|
| **Owner** | `StudentRequestService` |
| **Entry Points** | Student FSM flow (`student.py`) |
| **Dependencies** | `database.crud.create_student_request` (delegates to `upsert_student_request`) |
| **Business Rules** | Upsert: one active pending request per student; item ≥3 chars, ≤250; location ≥2, ≤100; date not in past |
| **Persistence** | `StudentRequest` table |
| **External** | None |

---

### Parent Travel Registration

| Property | Value |
|----------|-------|
| **Owner** | `ParentTravelService` |
| **Entry Points** | Parent FSM flow (`parent.py`) |
| **Dependencies** | `database.crud.create_parent_travel` (delegates to `upsert_parent_travel`) |
| **Business Rules** | Upsert: one active available travel per parent; location ≥2, ≤100; date not in past |
| **Persistence** | `ParentTravel` table |
| **External** | None |

---

### Automatic Matching

| Property | Value |
|----------|-------|
| **Owner** | `MatchingService` |
| **Entry Points** | Student FSM completion, Parent FSM completion |
| **Dependencies** | `services.matching.find_matches`, `database.crud.create_match`, `services.notifications.notify_admin_match` |
| **Business Rules** | Match on location (case-insensitive, trimmed) + school + date; exclude pairs with existing active/pending match; race-condition safe insert |
| **Persistence** | `Match` table |
| **External** | Telegram Bot API (admin notification) |

---

### Match Review (Admin)

| Property | Value |
|----------|-------|
| **Owner** | `MatchingService` |
| **Entry Points** | `/admin_matches` command, `approve_match_*` callback, `reject_match_*` callback |
| **Dependencies** | `database.crud.approve_match`, `database.crud.reject_match`, `services.notifications` |
| **Business Rules** | Only `PENDING_REVIEW` matches may be approved/rejected; approval sets statuses to `MATCHED`; rejection resets to `PENDING`/`AVAILABLE`; every decision logged to `AuditLog` |
| **Persistence** | `Match`, `StudentRequest`, `ParentTravel`, `AuditLog` |
| **External** | Telegram Bot API (student + parent notifications) |

---

### Health Check

| Property | Value |
|----------|-------|
| **Owner** | `HealthCheckService` |
| **Entry Points** | `/health` Telegram command |
| **Dependencies** | `database.db.async_session`, `bot.client.bot` |
| **Business Rules** | Admin-only; probe DB with `SELECT 1`; probe Telegram with `getMe` |
| **Persistence** | None |
| **External** | Database, Telegram Bot API |

---

## Extension Guide

### Adding a New Feature

1. **Define requirements** — What does the feature do? What rules apply?
2. **Identify the owner** — Create a new service in `services/` if no existing service owns this domain.
3. **Add CRUD functions** — Add persistence operations to `database/crud.py`.
4. **Create the service** — Implement the application workflow in the new service class.
5. **Add the handler** — Wire a new or updated handler in `bot/handlers/` that delegates to the service.
6. **Write tests** — Unit test the service; integration test the handler via pytest.
7. **Update this document** — Add the feature to the Feature Ownership Map.

**Example — adding a "Cancel Request" feature:**

```
New files/changes:
  services/cancellation_service.py   ← new application service
  database/crud.py                   ← add cancel_student_request()
  bot/handlers/student.py            ← add /cancel_request handler
  docs/architecture.md               ← update Feature Ownership Map
```

### Modifying an Existing Feature

1. Locate the owning service from the Feature Ownership Map.
2. Change the business rule in the service (never in the handler).
3. If the CRUD layer changes, update `database/crud.py`.
4. Update tests.
5. Update this document if ownership, dependencies, or persistence changes.

### Adding a New Interface

A key benefit of this architecture is that new interfaces (REST API, admin dashboard, mobile app) can reuse the existing application services without rewriting business logic:

```python
# REST API example
@app.post("/requests")
async def create_request(data: RequestSchema):
    await StudentRequestService.register_request(...)   # same service as Telegram bot
    await MatchingService.trigger_automatic_matching()  # same matching pipeline
```

### Deprecating a Feature

1. Mark the service method as deprecated with a docstring note.
2. Remove or stub the handler entry point.
3. Retain the CRUD functions if other services may still need them.
4. Remove from the Feature Ownership Map and update this document.

---

## Debugging Guide

Use the architectural layer to narrow the source of a bug:

| Symptom | Investigate First |
|---------|------------------|
| Bot command not responding / wrong reply text | **Interface Layer** — `bot/handlers/` |
| Wrong Telegram user receives a message | **Interface Layer** — check `telegram_id` extraction |
| Incorrect role assigned | **Application Layer** — `UserService.set_user_role` |
| Match not created when it should be | **Application Layer** — `MatchingService.trigger_automatic_matching` + `services.matching.find_matches` |
| Match created when it should not be (duplicate) | **Infrastructure Layer** — `database.crud.create_match` / `match_exists` |
| Wrong status after approve/reject | **Application Layer** — `MatchingService.approve_match` / `reject_match` |
| Notification not delivered | **Infrastructure Layer** — `services.notifications` retry logic, Telegram API |
| Data not persisting between restarts | **Infrastructure Layer** — `database.db` connection string, `database.crud` commit |
| Health check reports DB failure | **Infrastructure Layer** — `database.db.async_session`, `DATABASE_URL` config |
| Audit log entry missing | **Infrastructure Layer** — `database.crud.approve_match` / `reject_match` AuditLog insert |

### Layer Trace Example

```
Bug: Admin approves a match but the student receives no notification.

1. admin.py callback_approve_match()        ← Interface Layer: triggers correctly?
        ↓
2. MatchingService.approve_match()          ← Application Layer: returns match?
        ↓
3. notifications.notify_student_approved()  ← Infrastructure Layer: retry failure?
        ↓
4. _notification_bot.send_message()         ← External: Telegram API reachable?
```

---

## Testing Strategy

| Layer | Test Type | Location |
|-------|-----------|----------|
| Application Layer (services) | Unit / Integration | `tests/` |
| Infrastructure Layer (crud) | Integration | `tests/` |
| Critical Workflows | End-to-End | `tests/test_e2e_async.py`, `tests/test_end_to_end.py` |
| Admin Flows | E2E + QA | `tests/test_qa_plan.py`, `tests/test_qa_plan_extended.py` |
| Rejection Flow | Integration | `tests/test_rejection_flow_async.py` |
| Notifications | Unit | `tests/test_notifications_failure_async.py` |
| Duplicate Prevention | Integration | `tests/test_duplicate_prevention_async.py` |

**Run all tests (development):**

```powershell
$env:DATABASE_URL="sqlite+aiosqlite:///school_delivery.db"
$env:ENVIRONMENT="development"
.\venv\Scripts\pytest
```
