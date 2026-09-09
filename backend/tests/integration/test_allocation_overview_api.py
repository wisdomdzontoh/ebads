"""``GET /allocations/overview`` integration tests (role/permission audit Task 2).

The system-administrator, cross-facility, READ-ONLY oversight view — distinct from
``GET /allocations`` (dispatcher's own history, docs/01 §7) and ``GET /allocations/inbound``
(one facility's own queue, Task 3): this is the one endpoint with no facility_id boundary at
all, by design, and the one endpoint that must never accept a mutation regardless of who
calls it.
"""

from __future__ import annotations

from httpx import AsyncClient

from app.parameters import Role
from tests.integration.conftest import MakeUser

_LAT, _LON = 5.5826, -0.1880
_FACILITY_A = {
    "name": "Overview Test Facility A",
    "latitude": _LAT,
    "longitude": _LON,
    "tier": "tertiary",
    "supported_bed_types": ["general"],
    "contact_phone": "+233000000031",
}
# Far enough from A that a dispatch near B never routes to A instead (same displacement
# rationale as test_inbound_reservations_api.py's own Facility B).
_FACILITY_B = {
    "name": "Overview Test Facility B",
    "latitude": 6.00,
    "longitude": -0.60,
    "tier": "secondary",
    "supported_bed_types": ["general"],
    "contact_phone": "+233000000032",
}


async def _setup_facility(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    make_user: MakeUser,
    facility: dict,
) -> tuple[str, dict[str, str]]:
    created = await client.post("/api/v1/facilities", json=facility, headers=system_admin_headers)
    facility_id = created.json()["id"]
    _, staff_headers = await make_user(Role.FACILITY_STAFF, facility_id=facility_id)
    await client.patch(
        f"/api/v1/facilities/{facility_id}/beds",
        json={"bed_type": "general", "available": 5, "capacity": 20},
        headers=staff_headers,
    )
    return facility_id, staff_headers


async def _dispatch(
    client: AsyncClient, dispatcher_headers: dict[str, str], lat: float, lon: float
) -> dict:
    response = await client.post(
        "/api/v1/allocations",
        json={
            "patient_lat": lat,
            "patient_lon": lon,
            "urgency": "critical",
            "required_bed_type": "general",
        },
        headers=dispatcher_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmed"
    return body


async def test_system_administrator_sees_allocations_across_facilities(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    """The core oversight capability: a system_administrator (attached to no facility at
    all — the same NULL-facility_id invariant as a dispatcher, docs/02 §2.3) sees every
    facility's allocations in one call, each correctly labelled with its own facility name."""
    facility_a_id, _ = await _setup_facility(
        client, system_admin_headers, make_user, _FACILITY_A
    )
    facility_b_id, _ = await _setup_facility(
        client, system_admin_headers, make_user, _FACILITY_B
    )
    alloc_a = await _dispatch(client, dispatcher_headers, _LAT, _LON)
    alloc_b = await _dispatch(client, dispatcher_headers, 6.00, -0.60)
    assert alloc_a["recommended_facility"]["id"] == facility_a_id
    assert alloc_b["recommended_facility"]["id"] == facility_b_id

    response = await client.get("/api/v1/allocations/overview", headers=system_admin_headers)
    assert response.status_code == 200
    rows_by_id = {row["id"]: row for row in response.json()}
    assert alloc_a["id"] in rows_by_id
    assert alloc_b["id"] in rows_by_id
    assert rows_by_id[alloc_a["id"]]["facility_name"] == _FACILITY_A["name"]
    assert rows_by_id[alloc_b["id"]]["facility_name"] == _FACILITY_B["name"]
    # Newest first.
    ids_in_order = [row["id"] for row in response.json()]
    assert ids_in_order.index(alloc_b["id"]) < ids_in_order.index(alloc_a["id"])


async def test_system_administrator_overview_status_filter(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    await _setup_facility(client, system_admin_headers, make_user, _FACILITY_A)
    alloc = await _dispatch(client, dispatcher_headers, _LAT, _LON)

    confirmed_only = await client.get(
        "/api/v1/allocations/overview",
        params={"status": "confirmed"},
        headers=system_admin_headers,
    )
    assert confirmed_only.status_code == 200
    assert any(row["id"] == alloc["id"] for row in confirmed_only.json())

    arrived_only = await client.get(
        "/api/v1/allocations/overview",
        params={"status": "arrived"},
        headers=system_admin_headers,
    )
    assert arrived_only.status_code == 200
    assert all(row["id"] != alloc["id"] for row in arrived_only.json())


async def test_system_administrator_cannot_mutate_through_any_allocation_endpoint(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    """This is the test that proves read-only (role/permission audit): oversight
    (allocation_overview:read:all) grants no allocation:write of any scope, so every
    mutating endpoint 403s a system_administrator — acknowledge, revoke, refuse, and arrive,
    the full set FR20/FR22/FR24-27 define."""
    facility_id, _ = await _setup_facility(client, system_admin_headers, make_user, _FACILITY_A)
    alloc = await _dispatch(client, dispatcher_headers, _LAT, _LON)
    allocation_id = alloc["id"]

    acknowledge = await client.post(
        f"/api/v1/allocations/{allocation_id}/acknowledge", headers=system_admin_headers
    )
    assert acknowledge.status_code == 403

    revoke = await client.post(
        f"/api/v1/allocations/{allocation_id}/revoke",
        json={"reason": "oversight probe"},
        headers=system_admin_headers,
    )
    assert revoke.status_code == 403

    refuse = await client.post(
        f"/api/v1/allocations/{allocation_id}/refuse",
        json={"reason": "oversight probe"},
        headers=system_admin_headers,
    )
    assert refuse.status_code == 403

    arrive = await client.post(
        f"/api/v1/allocations/{allocation_id}/arrive", headers=system_admin_headers
    )
    assert arrive.status_code == 403


async def test_dispatcher_forbidden_from_overview_despite_holding_allocation_read_all(
    client: AsyncClient, dispatcher_headers: dict[str, str]
) -> None:
    """The distinguishing case: dispatcher already holds allocation:read:all (for its own
    GET /allocations / GET /allocations/{id}), but that grant is on the "allocation"
    resource, not "allocation_overview" — oversight is a distinct, system_administrator-only
    resource (0012_allocation_overview), so this must still 403."""
    response = await client.get("/api/v1/allocations/overview", headers=dispatcher_headers)
    assert response.status_code == 403


async def test_overview_without_auth_is_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/allocations/overview")
    assert response.status_code == 401
