"""``/allocations/{id}/revoke`` and ``/reallocate`` integration tests (FR24-27).

A reservation is a coordination claim, not a clinical entitlement: the facility retains
authority over its beds. These tests exercise the full loop — a facility revoking a held
reservation before arrival, the dispatcher being notified on two channels, and the
dispatcher redirecting to a different facility from their current (not original) position,
with the revoking facility excluded from the new candidate set.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import Notification
from app.domain.allocation.service import AllocationRequest, AllocationService
from app.domain.travel.live import LiveTravelTimeService
from app.parameters import BedType, NotificationChannel, Role, Urgency
from tests.integration.conftest import MakeUser

_LAT, _LON = 5.5826, -0.1880
_FACILITY_A = {
    "name": "Revocation Test Facility A",
    "latitude": _LAT,
    "longitude": _LON,
    "tier": "tertiary",
    "supported_bed_types": ["icu"],
    "contact_phone": "+233000000001",
}
# ~1.5 km from A — close enough that both are admissible candidates for a critical/icu
# request (R(critical) = 30 min), so which one wins is a genuine scoring outcome, not a
# hard-filter artefact.
_FACILITY_B = {
    "name": "Revocation Test Facility B",
    "latitude": 5.5940,
    "longitude": -0.1880,
    "tier": "tertiary",
    "supported_bed_types": ["icu"],
    "contact_phone": "+233000000002",
}


async def _confirmed_allocation_to_a(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> tuple[str, str, str, dict[str, str]]:
    """Register facilities A and B, staff A, and dispatch a confirmed allocation to A.

    B is registered with plenty of ICU beds but is *further* than A, so an unconstrained
    request still prefers A — the tests below rely on that to prove exclusion actually
    changes the outcome, not merely that B happens to win anyway.

    Returns (allocation_id, facility_a_id, facility_b_id, staff_a_headers).
    """
    facility_a = (
        await client.post("/api/v1/facilities", json=_FACILITY_A, headers=system_admin_headers)
    ).json()
    facility_b = (
        await client.post("/api/v1/facilities", json=_FACILITY_B, headers=system_admin_headers)
    ).json()
    _, staff_a_headers = await make_user(Role.FACILITY_STAFF, facility_id=facility_a["id"])
    await client.patch(
        f"/api/v1/facilities/{facility_a['id']}/beds",
        json={"bed_type": "icu", "available": 2, "capacity": 5},
        headers=staff_a_headers,
    )
    _, staff_b_headers = await make_user(Role.FACILITY_STAFF, facility_id=facility_b["id"])
    await client.patch(
        f"/api/v1/facilities/{facility_b['id']}/beds",
        json={"bed_type": "icu", "available": 3, "capacity": 5},
        headers=staff_b_headers,
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
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["recommended_facility"]["id"] == facility_a["id"]  # nearer, wins unconstrained
    return body["id"], facility_a["id"], facility_b["id"], staff_a_headers


async def test_revoke_releases_the_bed_and_writes_two_notifications(
    client: AsyncClient,
    db_session: AsyncSession,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    allocation_id, facility_a_id, _b, staff_a_headers = await _confirmed_allocation_to_a(
        client, system_admin_headers, dispatcher_headers, make_user
    )
    # allocate() already wrote one SMS notification to the facility at confirm time
    # (FR19) — the assertion below must count only the two revoke adds, not that baseline.
    before = (
        await db_session.scalars(
            select(Notification).where(Notification.allocation_id == allocation_id)
        )
    ).all()

    response = await client.post(
        f"/api/v1/allocations/{allocation_id}/revoke",
        json={"reason": "critical patient walked in, bed given to them"},
        headers=staff_a_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "revoked"

    facility_after = (
        await client.get(f"/api/v1/facilities/{facility_a_id}", headers=system_admin_headers)
    ).json()
    icu_after = next(b for b in facility_after["bed_counts"] if b["bed_type"] == "icu")
    assert icu_after["available"] == 2  # released back

    after = (
        await db_session.scalars(
            select(Notification).where(Notification.allocation_id == allocation_id)
        )
    ).all()
    new_notifications = [n for n in after if n.id not in {b.id for b in before}]
    channels = {n.channel for n in new_notifications}
    assert channels == {NotificationChannel.SMS, NotificationChannel.PUSH}
    assert len(new_notifications) == 2


async def test_revoking_an_arrived_allocation_is_409(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    allocation_id, _a, _b, staff_a_headers = await _confirmed_allocation_to_a(
        client, system_admin_headers, dispatcher_headers, make_user
    )
    arrive = await client.post(
        f"/api/v1/allocations/{allocation_id}/arrive", headers=dispatcher_headers
    )
    assert arrive.status_code == 200

    response = await client.post(
        f"/api/v1/allocations/{allocation_id}/revoke",
        json={"reason": "too late"},
        headers=staff_a_headers,
    )
    assert response.status_code == 409


async def test_revoke_by_dispatcher_is_404(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    """Separation of duties, matching /refuse's own precedent: only the receiving facility
    can revoke, not the dispatcher."""
    allocation_id, _a, _b, _staff = await _confirmed_allocation_to_a(
        client, system_admin_headers, dispatcher_headers, make_user
    )
    response = await client.post(
        f"/api/v1/allocations/{allocation_id}/revoke",
        json={"reason": "test"},
        headers=dispatcher_headers,
    )
    assert response.status_code == 404


async def test_reallocate_excludes_the_revoking_facility(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    allocation_id, facility_a_id, facility_b_id, staff_a_headers = await _confirmed_allocation_to_a(
        client, system_admin_headers, dispatcher_headers, make_user
    )
    revoke = await client.post(
        f"/api/v1/allocations/{allocation_id}/revoke",
        json={"reason": "critical patient walked in"},
        headers=staff_a_headers,
    )
    assert revoke.status_code == 200

    reallocate = await client.post(
        f"/api/v1/allocations/{allocation_id}/reallocate",
        json={"current_lat": _LAT, "current_lon": _LON},
        headers=dispatcher_headers,
    )
    assert reallocate.status_code == 200
    body = reallocate.json()
    assert body["status"] == "confirmed"
    # A still has a free bed (2 available after the revoke's release) and is nearer — an
    # unconstrained re-run would pick it again. It must not appear here.
    assert body["recommended_facility"]["id"] == facility_b_id
    assert body["recommended_facility"]["id"] != facility_a_id


async def test_supersession_chain_is_traversable(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    allocation_id, _a, _b, staff_a_headers = await _confirmed_allocation_to_a(
        client, system_admin_headers, dispatcher_headers, make_user
    )
    await client.post(
        f"/api/v1/allocations/{allocation_id}/revoke",
        json={"reason": "critical patient walked in"},
        headers=staff_a_headers,
    )
    reallocate = await client.post(
        f"/api/v1/allocations/{allocation_id}/reallocate",
        json={"current_lat": _LAT, "current_lon": _LON},
        headers=dispatcher_headers,
    )
    new_allocation_id = reallocate.json()["id"]

    audit = await client.get(
        f"/api/v1/allocations/{new_allocation_id}", headers=dispatcher_headers
    )
    assert audit.status_code == 200
    assert audit.json()["supersedes_allocation_id"] == allocation_id


async def test_reallocate_before_any_revocation_or_escalation_is_409(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    allocation_id, _a, _b, _staff = await _confirmed_allocation_to_a(
        client, system_admin_headers, dispatcher_headers, make_user
    )
    response = await client.post(
        f"/api/v1/allocations/{allocation_id}/reallocate",
        json={"current_lat": _LAT, "current_lon": _LON},
        headers=dispatcher_headers,
    )
    assert response.status_code == 409


async def test_reallocating_from_10km_along_the_route_yields_a_different_ranking(
    client: AsyncClient,
    db_session: AsyncSession,
    system_admin_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    """The urgency radius applies from the *current* position, not the original incident
    location (docs/01 §7, Task 2.3) — re-scoring from a materially different origin must be
    able to change which facility wins, not just re-confirm the original pick.
    """
    origin_lat, origin_lon = 5.60, -0.20
    # ~10 km north along a notional route (1 deg latitude =~ 111 km).
    displaced_lat, displaced_lon = origin_lat + 10 / 111, origin_lon

    near_origin = {
        "name": "Near Origin Facility",
        "latitude": origin_lat,
        "longitude": origin_lon + 0.01,  # ~1 km from the origin
        "tier": "tertiary",
        "supported_bed_types": ["general"],
        "contact_phone": "+233000000010",
    }
    near_displaced = {
        "name": "Near Displaced Facility",
        "latitude": displaced_lat,
        "longitude": displaced_lon + 0.01,  # ~1 km from the displaced position
        "tier": "tertiary",
        "supported_bed_types": ["general"],
        "contact_phone": "+233000000011",
    }
    facility_a = (
        await client.post("/api/v1/facilities", json=near_origin, headers=system_admin_headers)
    ).json()
    facility_b = (
        await client.post("/api/v1/facilities", json=near_displaced, headers=system_admin_headers)
    ).json()
    # PATCH .../beds is own_facility-scoped to facility staff/admin, not system_administrator
    # (docs/02 §2.2's permission matrix) — a facility-scoped account is required per facility.
    for facility in (facility_a, facility_b):
        _, staff_headers = await make_user(Role.FACILITY_STAFF, facility_id=facility["id"])
        beds = await client.patch(
            f"/api/v1/facilities/{facility['id']}/beds",
            json={"bed_type": "general", "available": 5, "capacity": 5},
            headers=staff_headers,
        )
        assert beds.status_code == 200

    service = AllocationService(db_session, LiveTravelTimeService(api_key=""))
    from_origin = await service.evaluate(
        AllocationRequest(
            patient_lat=origin_lat,
            patient_lon=origin_lon,
            required_bed_type=BedType.GENERAL,
            urgency=Urgency.STANDARD,
        )
    )
    from_displaced = await service.evaluate(
        AllocationRequest(
            patient_lat=displaced_lat,
            patient_lon=displaced_lon,
            required_bed_type=BedType.GENERAL,
            urgency=Urgency.STANDARD,
        )
    )

    assert from_origin.recommended is not None
    assert from_displaced.recommended is not None
    assert str(from_origin.recommended.facility_id) == facility_a["id"]
    assert str(from_displaced.recommended.facility_id) == facility_b["id"]
    assert from_origin.recommended.facility_id != from_displaced.recommended.facility_id
