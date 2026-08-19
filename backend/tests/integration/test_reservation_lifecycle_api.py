"""``/allocations/{id}/arrive`` `/acknowledge`, `/refuse`` integration tests (FR20, FR22).

Exercises the reservation lifecycle end to end through the real HTTP API: create a
confirmed allocation, then drive it through each terminal transition, checking the role
scoping (dispatcher for arrival, the receiving facility's own staff for
acknowledge/refuse) and the bed-availability side effect of a refusal.
"""

from __future__ import annotations

from httpx import AsyncClient

from app.parameters import Role
from tests.integration.conftest import MakeUser

_LAT, _LON = 5.5826, -0.1880
_FACILITY = {
    "name": "Lifecycle Test Facility",
    "latitude": _LAT,
    "longitude": _LON,
    "tier": "tertiary",
    "supported_bed_types": ["icu"],
    "contact_phone": "+233000000000",
}


async def _confirmed_allocation(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> tuple[str, str, dict[str, str]]:
    """Create a facility, staff it, and dispatch a confirmed allocation to it.

    Returns (allocation_id, facility_id, staff_headers).
    """
    created = await client.post(
        "/api/v1/facilities", json=_FACILITY, headers=system_admin_headers
    )
    facility_id = created.json()["id"]
    _, staff_headers = await make_user(Role.FACILITY_STAFF, facility_id=facility_id)
    await client.patch(
        f"/api/v1/facilities/{facility_id}/beds",
        json={"bed_type": "icu", "available": 2, "capacity": 5},
        headers=staff_headers,
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
    assert body["status"] == "confirmed"
    return body["id"], facility_id, staff_headers


async def test_arrival_marks_allocation_arrived(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    allocation_id, _facility_id, _staff = await _confirmed_allocation(
        client, system_admin_headers, dispatcher_headers, make_user
    )

    response = await client.post(
        f"/api/v1/allocations/{allocation_id}/arrive", headers=dispatcher_headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "arrived"


async def test_arrival_by_another_dispatcher_is_404(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    allocation_id, _facility_id, _staff = await _confirmed_allocation(
        client, system_admin_headers, dispatcher_headers, make_user
    )
    _, other_dispatcher_headers = await make_user(Role.DISPATCHER)

    response = await client.post(
        f"/api/v1/allocations/{allocation_id}/arrive", headers=other_dispatcher_headers
    )
    assert response.status_code == 404


async def test_arriving_twice_is_409(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    allocation_id, _facility_id, _staff = await _confirmed_allocation(
        client, system_admin_headers, dispatcher_headers, make_user
    )
    first = await client.post(
        f"/api/v1/allocations/{allocation_id}/arrive", headers=dispatcher_headers
    )
    assert first.status_code == 200
    second = await client.post(
        f"/api/v1/allocations/{allocation_id}/arrive", headers=dispatcher_headers
    )
    assert second.status_code == 409


async def test_acknowledge_records_timestamp_without_blocking_arrival(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    """FR20: acknowledgement is advisory — arrival succeeds with or without it."""
    allocation_id, _facility_id, staff_headers = await _confirmed_allocation(
        client, system_admin_headers, dispatcher_headers, make_user
    )

    ack = await client.post(
        f"/api/v1/allocations/{allocation_id}/acknowledge", headers=staff_headers
    )
    assert ack.status_code == 200
    assert ack.json()["acknowledged_at"] is not None
    assert ack.json()["confirmed"] is False  # "confirmed" means arrival, not acknowledgement

    arrive = await client.post(
        f"/api/v1/allocations/{allocation_id}/arrive", headers=dispatcher_headers
    )
    assert arrive.status_code == 200


async def test_acknowledge_by_a_different_facilitys_staff_is_404(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    allocation_id, _facility_id, _staff = await _confirmed_allocation(
        client, system_admin_headers, dispatcher_headers, make_user
    )
    other_facility = (
        await client.post(
            "/api/v1/facilities",
            json={**_FACILITY, "name": "Other Facility"},
            headers=system_admin_headers,
        )
    ).json()
    _, other_staff_headers = await make_user(Role.FACILITY_STAFF, facility_id=other_facility["id"])

    response = await client.post(
        f"/api/v1/allocations/{allocation_id}/acknowledge", headers=other_staff_headers
    )
    assert response.status_code == 404


async def test_refuse_releases_the_bed(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    allocation_id, facility_id, staff_headers = await _confirmed_allocation(
        client, system_admin_headers, dispatcher_headers, make_user
    )
    facility_before = (
        await client.get(f"/api/v1/facilities/{facility_id}", headers=system_admin_headers)
    ).json()
    icu_before = next(b for b in facility_before["bed_counts"] if b["bed_type"] == "icu")
    assert icu_before["available"] == 1  # 2 seeded, 1 reserved by the allocation

    response = await client.post(
        f"/api/v1/allocations/{allocation_id}/refuse",
        json={"reason": "no qualified staff on shift"},
        headers=staff_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "refused"

    facility_after = (
        await client.get(f"/api/v1/facilities/{facility_id}", headers=system_admin_headers)
    ).json()
    icu_after = next(b for b in facility_after["bed_counts"] if b["bed_type"] == "icu")
    assert icu_after["available"] == 2  # released back


async def test_refuse_by_dispatcher_is_404(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    """Separation of duties: only the receiving facility can refuse, not the dispatcher.

    A dispatcher does carry a coarse "allocation write" grant (needed to create/arrive their
    own allocations), so this is stopped by the facility-ownership check inside the handler
    (dispatcher.facility_id is None, never equal to a real facility id) rather than by
    ``require_permission`` itself — 404, consistent with every other ownership mismatch in
    this file (a dispatcher has no legitimate reason to learn the allocation even exists).
    """
    allocation_id, _facility_id, _staff = await _confirmed_allocation(
        client, system_admin_headers, dispatcher_headers, make_user
    )
    response = await client.post(
        f"/api/v1/allocations/{allocation_id}/refuse",
        json={"reason": "test"},
        headers=dispatcher_headers,
    )
    assert response.status_code == 404
