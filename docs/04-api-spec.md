# 04 — API Specification

> Source of truth: thesis §3.4, §3.6, §3.12. FastAPI + Pydantic v2; OpenAPI auto-generated at `/openapi.json`, Swagger UI at `/docs`. Base path: `/api/v1`.

## 1. Conventions
- JSON only; UTF-8; ISO-8601 timestamps (UTC).
- IDs are UUIDs.
- Validation errors → `422` with field-level detail (Pydantic default).
- Every mutating endpoint is idempotent where stated; allocation requests are **not** idempotent (each is a new event with audit).
- Auth `[IMPL]`: prototype uses a static API key header `X-API-Key`; full auth is out of scope (PRD §5).

## 2. Health
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/healthz` | liveness (process up) |
| GET | `/readyz` | readiness (DB reachable) |

## 3. Facilities (Facility Registry Service)

### `POST /api/v1/facilities`
Register a facility.
```json
{
  "name": "37 Military Hospital",
  "latitude": 5.5826, "longitude": -0.1880,
  "tier": "tertiary",
  "supported_bed_types": ["general", "icu", "maternity_specialist"],
  "contact_phone": "+233...",
  "active_data_source": "simulation"
}
```
→ `201` facility object (with `id`).

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/facilities` | list all (used for mobile cache sync); supports `?updated_since=` |
| GET | `/api/v1/facilities/{id}` | one facility |
| PUT | `/api/v1/facilities/{id}` | update static attributes |
| PATCH | `/api/v1/facilities/{id}/beds` | update live bed counts (non-simulation) |

`PATCH .../beds` body:
```json
{ "bed_type": "icu", "available": 3, "capacity": 12 }
```

## 4. Allocation (Emergency Request & Allocation Service)

### `POST /api/v1/allocations`
Submit an emergency; returns a recommendation **or** an escalation. This is the core endpoint.

Request:
```json
{
  "patient_lat": 5.6037, "patient_lon": -0.1870,
  "urgency": "critical",                       // critical | urgent | standard | null
  "required_bed_type": "icu",                  // general | icu | maternity_specialist
  "simulation_session_id": null                // set only for simulation events
}
```

Response — **allocated** (`200`):
```json
{
  "id": "uuid",
  "status": "allocated",
  "recommended_facility": {
    "id": "uuid", "name": "37 Military Hospital",
    "tier": "tertiary", "available_beds": 4,
    "travel_time_minutes": 12.4, "is_estimated_travel_time": false,
    "latitude": 5.5826, "longitude": -0.1880, "contact_phone": "+233..."
  },
  "algorithm_used": "urgency_adaptive",
  "weight_vector": { "w_t": 0.50, "w_b": 0.15, "w_c": 0.35 },
  "capability_match": 1.0,
  "candidates_evaluated": 7,
  "selection_reason": "Lowest urgency-adaptive score among 7 reachable facilities with an available ICU bed."
}
```

Response — **escalated** (`200`):
```json
{
  "id": "uuid",
  "status": "escalated",
  "recommended_facility": null,
  "requires_manual_decision": true,
  "nearest_within_radius": { "id": "uuid", "name": "...", "travel_time_minutes": 18.0, "available_beds": 0 },
  "nearest_available_outside_radius": { "id": "uuid", "name": "...", "travel_time_minutes": 41.0, "available_beds": 2 },
  "algorithm_used": "urgency_adaptive",
  "candidates_evaluated": 0,
  "selection_reason": "No reachable facility within R(critical)=30 min had an available ICU bed."
}
```

Notes:
- `algorithm_used` is decided by the Selector (§8 of [03-algorithms.md](./03-algorithms.md)).
- The engine **always** returns `200` with a recommendation or escalation; maps-API failure does not error — it sets `is_estimated_travel_time=true`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/allocations/{id}` | fetch one audit record |
| GET | `/api/v1/allocations` | list/filter audit records (`?status=`, `?from=`, `?to=`) |

## 5. Simulation (thesis §3.12)

### `POST /api/v1/simulation/sessions`
Create a session (seeds isolated bed state at the target occupancy).
```json
{
  "algorithm_config": "urgency_adaptive",   // greedy | weighted | urgency_adaptive
  "occupancy_scenario": 0.90,               // 0.75 | 0.90 | 1.00
  "events_planned": 100,
  "random_seed": 20260617,
  "weight_config": null,                    // null = defaults; object for sensitivity runs
  "radius_config": null,
  "capability_config": null
}
```
→ `201` session object.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/simulation/sessions/{id}/run` | **Automatic mode**: generate + process all planned events on the virtual clock; returns summary metrics |
| POST | `/api/v1/simulation/sessions/{id}/step` | **Interactive mode**: process one event and return the full decision trace (candidates, scores, selection) |
| GET | `/api/v1/simulation/sessions/{id}` | session config + status |
| GET | `/api/v1/simulation/sessions/{id}/results` | per-event records + aggregated metrics (ATBP, FRR, MCEE, CM) |

`step` response includes the decision trace for audit/illustration (thesis §3.12.2):
```json
{
  "event_index": 12,
  "candidates": [
    { "facility_id": "uuid", "travel_time_minutes": 9.1, "available_beds": 2,
      "t_hat": 0.10, "b_hat": 0.50, "c_hat": 1.0, "score": 0.272 }
  ],
  "selected_facility_id": "uuid",
  "algorithm_used": "urgency_adaptive",
  "weight_vector": { "w_t": 0.50, "w_b": 0.15, "w_c": 0.35 },
  "status": "allocated"
}
```

## 6. Error model
| Code | Meaning |
|------|---------|
| 400 | malformed request |
| 401 | missing/invalid API key `[IMPL]` |
| 404 | unknown id |
| 409 | simulation session already completed / state conflict |
| 422 | validation error (field detail) |
| 500 | unexpected (logged with correlation id) |

Allocation never returns 5xx for maps-API unavailability (fallback instead).

## 7. OpenAPI
- Schemas generated from Pydantic models; keep request/response models in `backend/app/api/schemas/`.
- `operationId`s are stable and descriptive (used by client/codegen).
- Examples (above) included in the schema so `/docs` is self-explanatory for future integrators.
