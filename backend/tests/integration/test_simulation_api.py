"""Simulation API endpoints (docs/04-api-spec.md §5, docs/12 §7).

Exercises the documented flow — create session → step (interactive trace, RB-5) → run
(automatic metrics) → results — plus the error model: 409 on re-running/over-stepping, 404 on
unknown ids, and 422 on an invalid occupancy or a not-yet-supported sensitivity override. A
fixed in-radius stub travel service is injected so decisions are deterministic and no
distance-matrix file is required.
"""

from __future__ import annotations

from fastapi import FastAPI
from httpx import AsyncClient

from app.api.routes.simulation import get_simulation_travel_service
from app.domain.travel.base import Coordinate, TravelTimeResult, TravelTimeService

_UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"
_ALL_BED_TYPES = ["general", "icu", "maternity_specialist"]


class _StubTravel(TravelTimeService):
    """Fixed, in-radius travel time so simulation decisions are deterministic in API tests."""

    async def travel_time(self, origin: Coordinate, destination: Coordinate) -> TravelTimeResult:
        return TravelTimeResult(minutes=5.0, is_estimated=False)


def _use_stub_travel(app: FastAPI) -> None:
    app.dependency_overrides[get_simulation_travel_service] = _StubTravel


async def _seed_facility(client: AsyncClient, capacity: int = 12) -> str:
    """Register one tertiary facility offering every bed type, each with ``capacity`` beds."""
    created = await client.post(
        "/api/v1/facilities",
        json={
            "name": "Sim Tertiary",
            "latitude": 5.60,
            "longitude": -0.20,
            "tier": "tertiary",
            "supported_bed_types": _ALL_BED_TYPES,
            "contact_phone": "+233000000000",
            "active_data_source": "simulation",
        },
    )
    facility_id = created.json()["id"]
    for bed_type in _ALL_BED_TYPES:
        await client.patch(
            f"/api/v1/facilities/{facility_id}/beds",
            json={"bed_type": bed_type, "available": capacity, "capacity": capacity},
        )
    return facility_id


async def _create_session(client: AsyncClient, occupancy: float = 0.75, events: int = 6) -> str:
    response = await client.post(
        "/api/v1/simulation/sessions",
        json={
            "algorithm_config": "urgency_adaptive",
            "occupancy_scenario": occupancy,
            "events_planned": events,
            "random_seed": 20260617,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_create_session_returns_pending_status(client: AsyncClient) -> None:
    """Creating a session returns it in the 'pending' state with no events processed."""
    await _seed_facility(client)
    session_id = await _create_session(client)

    fetched = await client.get(f"/api/v1/simulation/sessions/{session_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["status"] == "pending"
    assert body["events_processed"] == 0
    assert body["events_planned"] == 6


async def test_step_returns_decision_trace(app_under_test: FastAPI, client: AsyncClient) -> None:
    """Interactive step returns the full decision trace: candidates, scores, selection (RB-5)."""
    _use_stub_travel(app_under_test)
    facility_id = await _seed_facility(client)
    session_id = await _create_session(client)

    response = await client.post(f"/api/v1/simulation/sessions/{session_id}/step")
    assert response.status_code == 200, response.text
    trace = response.json()
    assert trace["event_index"] == 0
    assert trace["status"] == "allocated"
    assert trace["selected_facility_id"] == facility_id
    assert trace["algorithm_used"] == "urgency_adaptive"
    assert len(trace["candidates"]) >= 1
    candidate = trace["candidates"][0]
    assert set(candidate) >= {
        "facility_id",
        "travel_time_minutes",
        "available_beds",
        "t_hat",
        "b_hat",
        "c_hat",
        "score",
    }
    # Stepping advances progress by exactly one event.
    session = (await client.get(f"/api/v1/simulation/sessions/{session_id}")).json()
    assert session["events_processed"] == 1
    assert session["status"] == "in_progress"


async def test_run_then_results(app_under_test: FastAPI, client: AsyncClient) -> None:
    """Automatic run returns metrics; results returns every event + the aggregated metrics."""
    _use_stub_travel(app_under_test)
    await _seed_facility(client)
    session_id = await _create_session(client, events=6)

    run = await client.post(f"/api/v1/simulation/sessions/{session_id}/run")
    assert run.status_code == 200, run.text
    summary = run.json()
    assert summary["status"] == "completed"
    assert summary["events_processed"] == 6
    assert summary["metrics"]["events_total"] == 6

    results = await client.get(f"/api/v1/simulation/sessions/{session_id}/results")
    assert results.status_code == 200
    body = results.json()
    assert len(body["events"]) == 6
    assert body["session"]["status"] == "completed"
    assert body["metrics"]["events_total"] == 6


async def test_rerunning_a_completed_session_conflicts(
    app_under_test: FastAPI, client: AsyncClient
) -> None:
    """A second run on a session that already has events is a 409 (docs/04 §6)."""
    _use_stub_travel(app_under_test)
    await _seed_facility(client)
    session_id = await _create_session(client, events=3)

    assert (await client.post(f"/api/v1/simulation/sessions/{session_id}/run")).status_code == 200
    conflict = await client.post(f"/api/v1/simulation/sessions/{session_id}/run")
    assert conflict.status_code == 409


async def test_stepping_past_completion_conflicts(
    app_under_test: FastAPI, client: AsyncClient
) -> None:
    """Stepping a fully processed session is a 409 (docs/04 §6)."""
    _use_stub_travel(app_under_test)
    await _seed_facility(client)
    session_id = await _create_session(client, events=1)

    assert (await client.post(f"/api/v1/simulation/sessions/{session_id}/step")).status_code == 200
    conflict = await client.post(f"/api/v1/simulation/sessions/{session_id}/step")
    assert conflict.status_code == 409


async def test_unknown_session_returns_404(client: AsyncClient) -> None:
    """Reads and actions on an unknown session id return 404."""
    assert (await client.get(f"/api/v1/simulation/sessions/{_UNKNOWN_ID}")).status_code == 404
    assert (
        await client.post(f"/api/v1/simulation/sessions/{_UNKNOWN_ID}/run")
    ).status_code == 404
    assert (
        await client.post(f"/api/v1/simulation/sessions/{_UNKNOWN_ID}/step")
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/simulation/sessions/{_UNKNOWN_ID}/results")
    ).status_code == 404


async def test_invalid_occupancy_is_422(client: AsyncClient) -> None:
    """An occupancy outside the fixed scenario set is rejected at validation (docs/09 §12.5)."""
    response = await client.post(
        "/api/v1/simulation/sessions",
        json={
            "algorithm_config": "weighted",
            "occupancy_scenario": 0.5,
            "events_planned": 5,
            "random_seed": 1,
        },
    )
    assert response.status_code == 422


async def test_sensitivity_override_is_rejected(client: AsyncClient) -> None:
    """A non-null sensitivity override is rejected (applied in Phase 5, not silently ignored)."""
    response = await client.post(
        "/api/v1/simulation/sessions",
        json={
            "algorithm_config": "weighted",
            "occupancy_scenario": 0.75,
            "events_planned": 5,
            "random_seed": 1,
            "weight_config": {"w_t": 0.4, "w_b": 0.35, "w_c": 0.25},
        },
    )
    assert response.status_code == 422
