# SchoolRelay Rebuild — Implementation Summary (Pickup Branch)

> Branch: `Pickup`
> Date: 2026-07-21

## 1. What Changed

This branch replaces the legacy string-based exact-match delivery system with a **Fixed Hub Model** centered at Covenant University (CU), Ota. The rebuild touches domain models, persistence, matching logic, Telegram handlers, notifications, configuration, and infrastructure.

### 1.1 Files Removed

| File | Reason |
|------|--------|
| `services/matching.py` | Legacy SQL JOIN matcher; replaced by `matching/` package |
| `services/request_service.py` | Unused dead code; no handler/test imported it outside its own module |
| `services/travel_service.py` | Unused dead code; no handler/test imported it outside its own module |

### 1.2 Files Replaced

| Old File | New File | Summary |
|----------|----------|---------|
| `database/models.py` | `database/models.py` | Replaced `StudentRequest`, `ParentTravel`, `Match` with `Location`, `DriverTrip`, `DeliveryRequest`, `TripMatch` |
| `database/enums.py` | `database/enums.py` | Added `Direction`, `TripStatus`, `GeocodeSource`; redesigned status enums |
| `database/crud.py` | `database/crud.py` | New CRUD functions for all new entities |
| `services/matching_service.py` | `services/matching_service.py` | Orchestrates new `matching/engine.py` instead of old SQL matcher |
| `services/notifications.py` | `services/notifications.py` | New templates: chain-review for admin, Maps buttons for student/driver |
| `bot/handlers/student.py` | `bot/handlers/student.py` | Delivery-request flow with direction + Lagos location |
| `bot/handlers/parent.py` | `bot/handlers/parent.py` | Driver-trip flow with direction, no `can_carry_packages` boolean |
| `bot/handlers/admin.py` | `bot/handlers/admin.py` | Review card renders a chain, not a 1:1 pair |
| `bot/states/student_states.py` | `bot/states/student_states.py` | Added `direction` state; removed `destination_school` |
| `bot/states/parent_states.py` | `bot/states/parent_states.py` | Removed `can_carry_packages`; kept `direction` |
| `bot/keyboards/role_keyboard.py` | `bot/keyboards/role_keyboard.py` | Replaced `PARENT_BUTTON_TEXT` with `DRIVER_BUTTON_TEXT` |
| `config.py` | `config.py` | Added `DISTANCE_PROVIDER`, `MAX_TRIP_STOPS`, `OSRM_BASE_URL` |
| `docker-compose.yml` | `docker-compose.yml` | Added OSRM service |
| `requirements.txt` | `requirements.txt` | Added `httpx==0.27.0` |

### 1.3 Files Added

| File | Purpose |
|------|---------|
| `matching/__init__.py` | Package entry; exports public API |
| `matching/distance_base.py` | `DistanceProvider` ABC + `DistanceResult` dataclass |
| `matching/providers/__init__.py` | Provider package entry |
| `matching/providers/mock.py` | `MockDistanceProvider` for tests |
| `matching/providers/haversine.py` | `HaversineDistanceProvider` for offline/fast estimates |
| `matching/engine.py` | `MatchingEngine`: filter → proximity → nearest-neighbor chain build |
| `matching/distance.py` | Provider selection via `DISTANCE_PROVIDER` env var |
| `matching/maps.py` | Google Maps URL builders for student (point-to-point) and driver (multi-waypoint) |
| `bot/keyboards/direction_keyboard.py` | Direction selection keyboard |
| `migrations/versions/002_rebuild_delivery_schema.py` | Alembic revision: drops legacy tables, creates new schema |

## 2. New Domain Model

### 2.1 Enums

```python
class Direction(str, enum.Enum):
    OUTBOUND = "outbound"   # CU → Lagos
    INBOUND = "inbound"     # Lagos → CU

class TripStatus(str, enum.Enum):
    OPEN = "open"
    FULL = "full"
    MATCHED = "matched"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class RequestStatus(str, enum.Enum):
    PENDING = "pending"
    MATCHED = "matched"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class MatchStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"

class GeocodeSource(str, enum.Enum):
    MANUAL = "manual"
    NOMINATIM = "nominatim"
    GOOGLE = "google"
    OSRM = "osrm"
    MOCK = "mock"
```

### 2.2 Schema

| Table | Key Columns | Notes |
|-------|-------------|-------|
| `locations` | `id`, `raw_text`, `lat`, `lng`, `geocode_source`, `resolved_at` | Caches geocoded Lagos addresses |
| `driver_trips` | `id`, `user_id`, `direction`, `travel_date`, `primary_location_id`, `status`, `max_stops` | Replaces `parent_travels` |
| `delivery_requests` | `id`, `user_id`, `item_description`, `direction`, `location_id`, `travel_date`, `status` | Replaces `student_requests`; drops `destination_school` |
| `trip_matches` | `id`, `driver_trip_id`, `delivery_request_id`, `sequence_index`, `distance_from_previous_km`, `time_from_previous_min`, `status` | Replaces `matches`; one row per stop in chain |
| `audit_logs` | unchanged | `entity_type` extended to `"trip_match"` |
| `users` | unchanged | Role values now include `"driver"` |

Unique constraint: `(driver_trip_id, delivery_request_id)` on `trip_matches`.

## 3. Matching Engine Design

### 3.1 Filter Stage (SQL)

- `direction` must match between request and trip
- `travel_date` must match (day-only equality)
- Request status must be `PENDING`
- No existing `trip_match` for the pair in `PENDING_REVIEW` or `APPROVED`
- Trip status must be `OPEN`

### 3.2 Proximity Stage (Python)

- Distance from trip's `primary_location` to request's `location` must be `<= 8.0 km`
- Time is used as a secondary signal for logging and tiebreaking, not as an independent qualifying gate
- Candidates sorted by distance ascending

### 3.3 Chain Building (Nearest-Neighbor)

- Start at `primary_location`
- Repeatedly pick the nearest still-eligible request by distance from the last-added stop
- Stop when no eligible requests remain within 8 km OR chain reaches `max_stops` (default 4)
- Each stop gets a `sequence_index` (0-based)

### 3.4 Distance Provider Abstraction

| Provider | Use Case |
|----------|----------|
| `MockDistanceProvider` | Deterministic tests |
| `HaversineDistanceProvider` | Offline pre-filter / fallback |
| `OSRMDistanceProvider` | Self-hosted routing (TODO) |
| `GoogleMapsDistanceProvider` | Optional paid API (TODO) |

Selection via `DISTANCE_PROVIDER` env var (`mock` or `haversine` supported today).

## 4. Telegram UI Changes

- **Student**: Collects item description → direction (CU→Lagos / Lagos→CU) → Lagos location → date. On approval, receives a point-to-point Google Maps link.
- **Driver**: Collects direction → Lagos primary location → date. On approval, receives a multi-stop waypointed Google Maps link.
- **Admin**: Review card shows the full chain with per-stop distance/time, not a single 1:1 pair.

All messages use `parse_mode="HTML"` with `InlineKeyboardButton` URL buttons for Maps links.

## 5. Migration Strategy

### 5.1 Chosen Path

**Clean cutover** — the new Alembic revision `002_rebuild_delivery_schema.py`:
1. Creates `locations`, `driver_trips`, `delivery_requests`, `trip_matches`
2. Drops `student_requests`, `parent_travels`, `matches`
3. Preserves `users` and `audit_logs`

### 5.2 Alternative Path (Not Applied)

If live production data exists that must be preserved, a dual-write migration would:
1. Create new tables alongside old ones
2. Backfill legacy free-text locations into `locations` via geocoding
3. Map legacy rows → new entities
4. Drop old tables only after verification

The current revision does **not** implement this alternative. If needed, a new revision can be written on top of `002_rebuild_delivery_schema`.

## 6. Infrastructure Changes

### 6.1 docker-compose.yml

Added `osrm` service using `osrm/osrm-backend:latest`. Requires a one-time data-prep step to download and process the Nigeria/Lagos `.osm.pbf` extract (not included in this branch).

### 6.2 Config

New environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DISTANCE_PROVIDER` | `mock` | Active distance backend |
| `MAX_TRIP_STOPS` | `4` | Max stops per driver chain |
| `OSRM_BASE_URL` | `http://osrm:5000` | OSRM container endpoint |

## 7. Layer Conformance

The rebuild preserves the 4-layer architecture from `docs/architecture.md`:

```
Interface Layer      bot/handlers/
        ↓
Application Layer    services/matching_service.py, services/notifications.py
        ↓
Domain Layer         database/enums.py
        ↓
Infrastructure Layer database/crud.py, database/models.py, database/db.py
        ↓
External             matching/ (distance providers, maps), Telegram API, OSRM
```

Key rule: `matching/*` may depend on `database/models.py` and `config.py` only. It must never import from `bot/handlers/*`. Handlers call `MatchingService`, which calls `matching/engine.py`.

## 8. Open Items / Next Steps

1. **Geocoding flow**: `get_or_create_location` currently uses mock coordinates (`6.5244, 3.3792`). A real geocoding provider (Nominatim, Google Geocoding, or manual admin entry) must be wired in before production use.
2. **OSRM data prep**: The `osrm-data` volume mount exists in `docker-compose.yml` but the `.osm.pbf` extract and preprocessing commands are not included. See OSRM documentation for `osrm-extract`, `osrm-partition`, `osrm-customize`.
3. **OSRM provider implementation**: `matching/providers/osrm.py` is not yet written. It should call `OSRM_BASE_URL/route/v1/driving/...` using `httpx`.
4. **Tests**: Existing tests import `services.matching.find_matches` and legacy models. They must be rewritten against the new `matching/engine.py` and new models. `matching/providers/mock.py` is ready to support deterministic test fixtures.
5. **Split-segment UX**: When eligible requests exceed `max_stops`, the engine currently stops at the cap. Whether excess requests become a second linked trip or require admin intervention is a product decision not yet implemented.
6. **Approval/notification Maps links**: `MatchingService.approve_match` builds Maps links, but the notification functions currently accept them as optional parameters. Verify the exact UX with the team.
