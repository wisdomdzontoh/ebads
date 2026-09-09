"""Facility-administrator/facility-staff allocation parity (role/permission audit Task 3).

``facility_administrator`` is supposed to be a strict superset of ``facility_staff`` — the
0011 migration grants it the same ``allocation:read``/``allocation:write`` at
``own_facility`` scope facility_staff already held. Confirms that grant alone is sufficient
(the routes' own dependencies — ``FacilityReaderDep``/``FacilityWriterDep`` — check the
*permission*, not the role name, so no route code needed to change) and that facility
scoping still correctly refuses a different facility's allocations.

``POST /{id}/arrive`` is deliberately NOT included among the "should succeed" endpoints
here even though the audit brief's Task 3 listed it: that endpoint is dispatcher-only by
design (FR22 — the dispatcher, not the facility, confirms the patient physically arrived;
``DispatcherDep`` in app/api/routes/allocations.py, unrelated to any own_facility grant) and
always has been, for facility_staff too. What's tested instead is that facility_administrator
gets the exact same result facility_staff already gets — parity, just not the direction the
brief's wording implied. See the audit report for the full explanation.
"""

from __future__ import annotations

from httpx import AsyncClient

from app.parameters import Role
from tests.integration.conftest import MakeUser

_LAT, _LON = 5.5826, -0.1880
_FACILITY_A = {
    "name": "Parity Test Facility A",
    "latitude": _LAT,
    "longitude": _LON,
    "tier": "tertiary",
    "supported_bed_types": ["general"],
    "contact_phone": "+233000000041",
}
_FACILITY_B = {
    "name": "Parity Test Facility B",
    "latitude": 6.00,
    "longitude": -0.60,
    "tier": "secondary",
    "supported_bed_types": ["general"],
    "contact_phone": "+233000000042",
}


async def _setup_facility(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    make_user: MakeUser,
    facility: dict,
    role: Role,
) -> tuple[str, dict[str, str]]:
    """Register a facility, staff it (facility_staff — needed to set bed counts regardless
    of which role the test is actually probing), and separately mint the requested role's
    headers for that same facility."""
    created = await client.post("/api/v1/facilities", json=facility, headers=system_admin_headers)
    facility_id = created.json()["id"]
    _, staff_headers = await make_user(Role.FACILITY_STAFF, facility_id=facility_id)
    await client.patch(
        f"/api/v1/facilities/{facility_id}/beds",
        json={"bed_type": "general", "available": 5, "capacity": 20},
        headers=staff_headers,
    )
    if role == Role.FACILITY_STAFF:
        return facility_id, staff_headers
    _, role_headers = await make_user(role, facility_id=facility_id)
    return facility_id, role_headers


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


async def test_facility_administrator_sees_only_own_facility_inbound(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    facility_a_id, admin_a_headers = await _setup_facility(
        client, system_admin_headers, make_user, _FACILITY_A, Role.FACILITY_ADMINISTRATOR
    )
    facility_b_id, _ = await _setup_facility(
        client, system_admin_headers, make_user, _FACILITY_B, Role.FACILITY_STAFF
    )
    alloc_a = await _dispatch(client, dispatcher_headers, _LAT, _LON)
    alloc_b = await _dispatch(client, dispatcher_headers, 6.00, -0.60)
    assert alloc_a["recommended_facility"]["id"] == facility_a_id
    assert alloc_b["recommended_facility"]["id"] == facility_b_id

    response = await client.get("/api/v1/allocations/inbound", headers=admin_a_headers)
    assert response.status_code == 200
    ids = [row["allocation_id"] for row in response.json()]
    assert alloc_a["id"] in ids
    assert alloc_b["id"] not in ids


async def test_facility_administrator_can_acknowledge_and_revoke_own_facility(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    facility_id, admin_headers = await _setup_facility(
        client, system_admin_headers, make_user, _FACILITY_A, Role.FACILITY_ADMINISTRATOR
    )
    alloc = await _dispatch(client, dispatcher_headers, _LAT, _LON)
    allocation_id = alloc["id"]

    acknowledge = await client.post(
        f"/api/v1/allocations/{allocation_id}/acknowledge", headers=admin_headers
    )
    assert acknowledge.status_code == 200
    assert acknowledge.json()["acknowledged_at"] is not None

    revoke = await client.post(
        f"/api/v1/allocations/{allocation_id}/revoke",
        json={"reason": "parity test"},
        headers=admin_headers,
    )
    assert revoke.status_code == 200
    assert revoke.json()["status"] == "revoked"
    assert revoke.json()["revocation_reason"] == "parity test"


async def test_facility_administrator_refused_for_another_facility(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    facility_a_id, _ = await _setup_facility(
        client, system_admin_headers, make_user, _FACILITY_A, Role.FACILITY_STAFF
    )
    _, admin_b_headers = await _setup_facility(
        client, system_admin_headers, make_user, _FACILITY_B, Role.FACILITY_ADMINISTRATOR
    )
    alloc = await _dispatch(client, dispatcher_headers, _LAT, _LON)
    assert alloc["recommended_facility"]["id"] == facility_a_id
    allocation_id = alloc["id"]

    acknowledge = await client.post(
        f"/api/v1/allocations/{allocation_id}/acknowledge", headers=admin_b_headers
    )
    assert acknowledge.status_code == 404

    revoke = await client.post(
        f"/api/v1/allocations/{allocation_id}/revoke",
        json={"reason": "should not apply"},
        headers=admin_b_headers,
    )
    assert revoke.status_code == 404


async def test_facility_administrator_and_facility_staff_get_the_same_result_on_arrive(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    """POST /{id}/arrive is dispatcher-only by design (FR22) — confirms neither facility
    role can call it, and that this was ALREADY true for facility_staff before this audit
    (i.e. facility_administrator's identical 403 is genuine parity, not a regression)."""
    facility_id, admin_headers = await _setup_facility(
        client, system_admin_headers, make_user, _FACILITY_A, Role.FACILITY_ADMINISTRATOR
    )
    _, staff_headers = await make_user(Role.FACILITY_STAFF, facility_id=facility_id)
    alloc = await _dispatch(client, dispatcher_headers, _LAT, _LON)
    allocation_id = alloc["id"]

    admin_arrive = await client.post(
        f"/api/v1/allocations/{allocation_id}/arrive", headers=admin_headers
    )
    staff_arrive = await client.post(
        f"/api/v1/allocations/{allocation_id}/arrive", headers=staff_headers
    )
    assert admin_arrive.status_code == 403
    assert staff_arrive.status_code == 403
    assert admin_arrive.status_code == staff_arrive.status_code


async def test_facility_staff_behaviour_is_unchanged(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    """Sanity check: facility_staff's own pre-existing capabilities (0005/0010) are
    untouched by adding facility_administrator's grants (0011) — acknowledge/revoke still
    work exactly as before."""
    facility_id, staff_headers = await _setup_facility(
        client, system_admin_headers, make_user, _FACILITY_A, Role.FACILITY_STAFF
    )
    alloc = await _dispatch(client, dispatcher_headers, _LAT, _LON)
    allocation_id = alloc["id"]

    inbound = await client.get("/api/v1/allocations/inbound", headers=staff_headers)
    assert inbound.status_code == 200
    assert any(row["allocation_id"] == allocation_id for row in inbound.json())

    acknowledge = await client.post(
        f"/api/v1/allocations/{allocation_id}/acknowledge", headers=staff_headers
    )
    assert acknowledge.status_code == 200

    revoke = await client.post(
        f"/api/v1/allocations/{allocation_id}/revoke",
        json={"reason": "unchanged behaviour check"},
        headers=staff_headers,
    )
    assert revoke.status_code == 200
