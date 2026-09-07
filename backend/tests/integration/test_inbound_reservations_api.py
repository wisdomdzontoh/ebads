"""``GET /allocations/inbound`` integration tests (Task 3, docs/02 §3.5-3.6, FR20).

The facility-staff inbound queue: active (confirmed) reservations for the signed-in
facility only, sorted by urgency then ETA ascending, dropping an item the moment it leaves
the confirmed state (acknowledged is advisory and does not remove it; arrival/revocation do).
"""

from __future__ import annotations

from httpx import AsyncClient

from app.parameters import Role
from tests.integration.conftest import MakeUser

_LAT, _LON = 5.5826, -0.1880
_FACILITY_A = {
    "name": "Inbound Test Facility A",
    "latitude": _LAT,
    "longitude": _LON,
    "tier": "tertiary",
    "supported_bed_types": ["general"],
    "contact_phone": "+233000000021",
}
# >90 min from Facility A (R(standard), the widest radius) — deliberately outside every
# urgency tier's hard filter, not merely farther: a closer-but-still-admissible B interacts
# with bed-count normalisation once A's beds start depleting (the same tertiary-vs-secondary,
# bed-scarcity-vs-capability-match effect documented in analysis/chapter4_evidence.md §9/§14),
# which would make facility selection itself the thing under test here, not the inbound
# endpoint's scoping/sorting.
_FACILITY_B = {
    "name": "Inbound Test Facility B",
    "latitude": 6.00,
    "longitude": -0.60,
    "tier": "secondary",
    "supported_bed_types": ["general"],
    "contact_phone": "+233000000022",
}


async def _setup_facility(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    make_user: MakeUser,
    facility: dict,
    available: int = 5,
) -> tuple[str, dict[str, str]]:
    """Register a facility, staff it, and set its general beds. Returns (id, staff_headers)."""
    created = await client.post("/api/v1/facilities", json=facility, headers=system_admin_headers)
    facility_id = created.json()["id"]
    _, staff_headers = await make_user(Role.FACILITY_STAFF, facility_id=facility_id)
    await client.patch(
        f"/api/v1/facilities/{facility_id}/beds",
        json={"bed_type": "general", "available": available, "capacity": 20},
        headers=staff_headers,
    )
    return facility_id, staff_headers


async def _dispatch(
    client: AsyncClient, dispatcher_headers: dict[str, str], urgency: str, lat_offset: float
) -> dict:
    response = await client.post(
        "/api/v1/allocations",
        json={
            "patient_lat": _LAT + lat_offset,
            "patient_lon": _LON,
            "urgency": urgency,
            "required_bed_type": "general",
        },
        headers=dispatcher_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmed"
    return body


async def test_inbound_list_is_scoped_to_the_facility_and_sorted(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    facility_a_id, staff_a_headers = await _setup_facility(
        client, system_admin_headers, make_user, _FACILITY_A
    )
    facility_b_id, staff_b_headers = await _setup_facility(
        client, system_admin_headers, make_user, _FACILITY_B
    )
    assert facility_a_id != facility_b_id

    # Two critical (different ETAs, to prove the within-tier tie-break), one urgent, one
    # standard — all routed to facility A (facility B has no admissible candidate nearby).
    near_critical = await _dispatch(client, dispatcher_headers, "critical", 0.001)
    far_critical = await _dispatch(client, dispatcher_headers, "critical", 0.01)
    urgent = await _dispatch(client, dispatcher_headers, "urgent", 0.005)
    standard = await _dispatch(client, dispatcher_headers, "standard", 0.02)
    for body in (near_critical, far_critical, urgent, standard):
        assert body["recommended_facility"]["id"] == facility_a_id

    response = await client.get("/api/v1/allocations/inbound", headers=staff_a_headers)
    assert response.status_code == 200
    ids = [row["allocation_id"] for row in response.json()]
    assert ids == [near_critical["id"], far_critical["id"], urgent["id"], standard["id"]]

    # Every row carries what the page needs to render.
    first = response.json()[0]
    assert first["urgency"] == "critical"
    assert first["required_bed_type"] == "general"
    assert first["confirmed"] is False
    assert first["acknowledged_at"] is None
    assert "expires_at" in first and "reservation_id" in first

    # Facility B's own queue is empty — none of the above were routed to it.
    b_response = await client.get("/api/v1/allocations/inbound", headers=staff_b_headers)
    assert b_response.status_code == 200
    assert b_response.json() == []


async def test_inbound_list_drops_an_item_once_acknowledged_is_still_shown(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    """Acknowledgement is advisory (FR20) — it must not remove the row."""
    facility_id, staff_headers = await _setup_facility(
        client, system_admin_headers, make_user, _FACILITY_A
    )
    allocation = await _dispatch(client, dispatcher_headers, "critical", 0.001)

    ack = await client.post(
        f"/api/v1/allocations/{allocation['id']}/acknowledge", headers=staff_headers
    )
    assert ack.status_code == 200

    response = await client.get("/api/v1/allocations/inbound", headers=staff_headers)
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["allocation_id"] == allocation["id"]
    assert rows[0]["acknowledged_at"] is not None


async def test_inbound_list_drops_an_item_once_revoked(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    facility_id, staff_headers = await _setup_facility(
        client, system_admin_headers, make_user, _FACILITY_A
    )
    allocation = await _dispatch(client, dispatcher_headers, "critical", 0.001)

    revoke = await client.post(
        f"/api/v1/allocations/{allocation['id']}/revoke",
        json={"reason": "test"},
        headers=staff_headers,
    )
    assert revoke.status_code == 200

    response = await client.get("/api/v1/allocations/inbound", headers=staff_headers)
    assert response.json() == []


async def test_inbound_list_drops_an_item_once_arrived(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    facility_id, staff_headers = await _setup_facility(
        client, system_admin_headers, make_user, _FACILITY_A
    )
    allocation = await _dispatch(client, dispatcher_headers, "critical", 0.001)

    arrive = await client.post(
        f"/api/v1/allocations/{allocation['id']}/arrive", headers=dispatcher_headers
    )
    assert arrive.status_code == 200

    response = await client.get("/api/v1/allocations/inbound", headers=staff_headers)
    assert response.json() == []


async def test_inbound_list_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/allocations/inbound")
    assert response.status_code == 401


async def test_inbound_list_as_dispatcher_is_empty_not_another_facilitys_data(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    """A dispatcher has ``allocation:read:all`` (docs/02 §2.2) so the permission layer admits
    the call, but has no ``facility_id`` — the query must match nothing, never leak another
    facility's queue (docs/01 §4)."""
    await _setup_facility(client, system_admin_headers, make_user, _FACILITY_A)
    await _dispatch(client, dispatcher_headers, "critical", 0.001)

    response = await client.get("/api/v1/allocations/inbound", headers=dispatcher_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_inbound_list_as_system_administrator_is_403(
    client: AsyncClient, system_admin_headers: dict[str, str]
) -> None:
    """system_administrator has no ``allocation`` grant at all (docs/02 §2.2)."""
    response = await client.get("/api/v1/allocations/inbound", headers=system_admin_headers)
    assert response.status_code == 403
