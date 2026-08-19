"""POST/GET /allocations integration tests (docs/04 §4, docs/12 §7).

Covers the happy path with full audit persistence, the escalation shape, the maps-failure
fallback flag (via an overridden travel service), and the GET audit endpoints. Since
Increment 1, ``/allocations`` is dispatcher-only (facility setup, done here via a
system_administrator + a facility_staff account it provisions, is a separate concern —
docs/01 §4 separation of duties).
"""

from __future__ import annotations

from fastapi import FastAPI
from httpx import AsyncClient

from app.api.routes.allocations import get_travel_service
from app.domain.travel.base import Coordinate, TravelTimeResult, TravelTimeService
from app.parameters import Role
from tests.integration.conftest import MakeUser

# A facility co-located with the patient, so Haversine travel time is 0 (always within radius).
_LAT, _LON = 5.5826, -0.1880
_FACILITY = {
    "name": "Test Tertiary",
    "latitude": _LAT,
    "longitude": _LON,
    "tier": "tertiary",
    "supported_bed_types": ["icu"],
    "contact_phone": "+233000000000",
}


class _StubTravel(TravelTimeService):
    """Fixed travel time + estimated flag, to make API tests deterministic."""

    def __init__(self, minutes: float, is_estimated: bool) -> None:
        self._minutes = minutes
        self._is_estimated = is_estimated

    async def travel_time(self, origin: Coordinate, destination: Coordinate) -> TravelTimeResult:
        return TravelTimeResult(minutes=self._minutes, is_estimated=self._is_estimated)


async def _create_facility_with_icu_beds(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    make_user: MakeUser,
    available: int = 4,
) -> str:
    """Create a facility (system_administrator) and set its ICU beds (its own staff)."""
    created = await client.post(
        "/api/v1/facilities", json=_FACILITY, headers=system_admin_headers
    )
    facility_id = created.json()["id"]
    _, staff_headers = await make_user(Role.FACILITY_STAFF, facility_id=facility_id)
    await client.patch(
        f"/api/v1/facilities/{facility_id}/beds",
        json={"bed_type": "icu", "available": available, "capacity": 12},
        headers=staff_headers,
    )
    return facility_id


async def test_allocation_happy_path_persists_audit(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    facility_id = await _create_facility_with_icu_beds(client, system_admin_headers, make_user)

    response = await client.post(
        "/api/v1/allocations",
        json={
            "patient_lat": _LAT,
            "patient_lon": _LON,
            "urgency": "critical",
            "required_bed_type": "icu",
        },
        headers=dispatcher_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "allocated"
    assert body["recommended_facility"]["id"] == facility_id
    assert body["algorithm_used"] == "urgency_adaptive"
    assert body["weight_vector"] == {"w_t": 0.50, "w_b": 0.10, "w_c": 0.40}
    assert body["candidates_evaluated"] == 1

    # Audit record is persisted and fetchable by the same dispatcher.
    fetched = await client.get(f"/api/v1/allocations/{body['id']}", headers=dispatcher_headers)
    assert fetched.status_code == 200
    record = fetched.json()
    assert record["status"] == "allocated"
    assert record["recommended_facility_id"] == facility_id
    assert record["weight_vector"] == {"w_t": 0.50, "w_b": 0.10, "w_c": 0.40}


async def test_create_allocation_without_auth_is_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/allocations",
        json={"patient_lat": _LAT, "patient_lon": _LON, "required_bed_type": "icu"},
    )
    assert response.status_code == 401


async def test_create_allocation_as_facility_staff_is_403(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    """FR18's mirror image: only a dispatcher may submit a request."""
    facility_id = await _create_facility_with_icu_beds(client, system_admin_headers, make_user)
    _, non_dispatcher_headers = await make_user(Role.FACILITY_STAFF, facility_id=facility_id)
    response = await client.post(
        "/api/v1/allocations",
        json={"patient_lat": _LAT, "patient_lon": _LON, "required_bed_type": "icu"},
        headers=non_dispatcher_headers,
    )
    assert response.status_code == 403


async def test_allocation_escalates_when_no_bed(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    facility_id = await _create_facility_with_icu_beds(
        client, system_admin_headers, make_user, available=0
    )

    response = await client.post(
        "/api/v1/allocations",
        json={
            "patient_lat": _LAT,
            "patient_lon": _LON,
            "urgency": "critical",
            "required_bed_type": "icu",
        },
        headers=dispatcher_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "escalated"
    assert body["recommended_facility"] is None
    assert body["requires_manual_decision"] is True
    assert body["candidates_evaluated"] == 0
    # The facility is within radius but has no bed -> it is the within-radius fallback.
    assert body["nearest_within_radius"]["id"] == facility_id
    assert body["nearest_available_outside_radius"] is None


async def test_maps_failure_sets_estimated_flag(
    app_under_test: FastAPI,
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    """A fallback (estimated) travel time propagates the flag to response + audit (docs/12 §7)."""
    app_under_test.dependency_overrides[get_travel_service] = lambda: _StubTravel(
        minutes=5.0, is_estimated=True
    )
    await _create_facility_with_icu_beds(client, system_admin_headers, make_user)

    response = await client.post(
        "/api/v1/allocations",
        json={
            "patient_lat": _LAT,
            "patient_lon": _LON,
            "urgency": "critical",
            "required_bed_type": "icu",
        },
        headers=dispatcher_headers,
    )
    body = response.json()
    assert body["status"] == "allocated"
    assert body["recommended_facility"]["is_estimated_travel_time"] is True

    record = (
        await client.get(f"/api/v1/allocations/{body['id']}", headers=dispatcher_headers)
    ).json()
    assert record["is_estimated_travel_time"] is True


async def test_working_maps_clears_estimated_flag(
    app_under_test: FastAPI,
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    app_under_test.dependency_overrides[get_travel_service] = lambda: _StubTravel(
        minutes=5.0, is_estimated=False
    )
    await _create_facility_with_icu_beds(client, system_admin_headers, make_user)

    response = await client.post(
        "/api/v1/allocations",
        json={
            "patient_lat": _LAT,
            "patient_lon": _LON,
            "urgency": "critical",
            "required_bed_type": "icu",
        },
        headers=dispatcher_headers,
    )
    assert response.json()["recommended_facility"]["is_estimated_travel_time"] is False


async def test_missing_urgency_uses_weighted_fallback(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    await _create_facility_with_icu_beds(client, system_admin_headers, make_user)
    response = await client.post(
        "/api/v1/allocations",
        json={"patient_lat": _LAT, "patient_lon": _LON, "required_bed_type": "icu"},
        headers=dispatcher_headers,
    )
    assert response.status_code == 200
    assert response.json()["algorithm_used"] == "weighted"


async def test_get_unknown_allocation_returns_404(
    client: AsyncClient, dispatcher_headers: dict[str, str]
) -> None:
    response = await client.get(
        "/api/v1/allocations/00000000-0000-0000-0000-000000000000", headers=dispatcher_headers
    )
    assert response.status_code == 404


async def test_get_another_dispatchers_allocation_returns_404(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    """A dispatcher may only read their own request history (PRD §2)."""
    await _create_facility_with_icu_beds(client, system_admin_headers, make_user)
    created = await client.post(
        "/api/v1/allocations",
        json={"patient_lat": _LAT, "patient_lon": _LON, "required_bed_type": "icu"},
        headers=dispatcher_headers,
    )
    _, other_dispatcher_headers = await make_user(Role.DISPATCHER)
    response = await client.get(
        f"/api/v1/allocations/{created.json()['id']}", headers=other_dispatcher_headers
    )
    assert response.status_code == 404


async def test_list_allocations_filters_by_status(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    await _create_facility_with_icu_beds(client, system_admin_headers, make_user)
    await client.post(
        "/api/v1/allocations",
        json={
            "patient_lat": _LAT,
            "patient_lon": _LON,
            "urgency": "critical",
            "required_bed_type": "icu",
        },
        headers=dispatcher_headers,
    )
    allocated = await client.get(
        "/api/v1/allocations", params={"status": "allocated"}, headers=dispatcher_headers
    )
    assert allocated.status_code == 200
    assert len(allocated.json()) == 1
    escalated = await client.get(
        "/api/v1/allocations", params={"status": "escalated"}, headers=dispatcher_headers
    )
    assert escalated.json() == []


async def test_unknown_simulation_session_returns_404(
    client: AsyncClient, dispatcher_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/allocations",
        json={
            "patient_lat": _LAT,
            "patient_lon": _LON,
            "urgency": "critical",
            "required_bed_type": "icu",
            "simulation_session_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=dispatcher_headers,
    )
    assert response.status_code == 404
