"""Facility Registry CRUD + seed integration tests (docs/04 §3; Phase 1 acceptance).

Covers the happy paths and the documented error/invariant behaviour for the
``/facilities`` endpoints, plus RB-2: the seed script loads exactly 24 facilities, each with
a tier, supported bed types, and capacity. Since Increment 1, every endpoint requires an
authenticated, role-appropriate caller (docs/01 §4) — ``POST`` is system_administrator only
(the real onboarding path is ``/registrations``); ``PUT``/``PATCH .../beds`` require a
facility_administrator/facility_staff scoped to that specific facility.
"""

from __future__ import annotations

from httpx import AsyncClient

from app.parameters import Role
from tests.integration.conftest import MakeUser, run_seed_script

# A minimal valid facility payload reused across tests.
_PAYLOAD = {
    "name": "37 Military Hospital",
    "latitude": 5.5826,
    "longitude": -0.1880,
    "tier": "tertiary",
    "supported_bed_types": ["general", "icu", "maternity_specialist"],
    "contact_phone": "+233302776111",
}


async def test_create_then_get_facility(
    client: AsyncClient, system_admin_headers: dict[str, str]
) -> None:
    created = await client.post("/api/v1/facilities", json=_PAYLOAD, headers=system_admin_headers)
    assert created.status_code == 201
    body = created.json()
    assert body["id"]
    assert body["tier"] == "tertiary"
    assert body["bed_counts"] == []  # no beds until PATCH .../beds

    fetched = await client.get(f"/api/v1/facilities/{body['id']}", headers=system_admin_headers)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == _PAYLOAD["name"]


async def test_create_without_auth_is_401(client: AsyncClient) -> None:
    response = await client.post("/api/v1/facilities", json=_PAYLOAD)
    assert response.status_code == 401


async def test_create_as_dispatcher_is_403(
    client: AsyncClient, dispatcher_headers: dict[str, str]
) -> None:
    response = await client.post("/api/v1/facilities", json=_PAYLOAD, headers=dispatcher_headers)
    assert response.status_code == 403


async def test_get_unknown_facility_returns_404(
    client: AsyncClient, system_admin_headers: dict[str, str]
) -> None:
    response = await client.get(
        "/api/v1/facilities/00000000-0000-0000-0000-000000000000", headers=system_admin_headers
    )
    assert response.status_code == 404


async def test_list_facilities_sorted_by_name(
    client: AsyncClient, system_admin_headers: dict[str, str]
) -> None:
    await client.post(
        "/api/v1/facilities",
        json={**_PAYLOAD, "name": "Zenith Clinic"},
        headers=system_admin_headers,
    )
    await client.post(
        "/api/v1/facilities",
        json={**_PAYLOAD, "name": "Alpha Clinic"},
        headers=system_admin_headers,
    )
    response = await client.get("/api/v1/facilities", headers=system_admin_headers)
    assert response.status_code == 200
    names = [f["name"] for f in response.json()]
    assert names == ["Alpha Clinic", "Zenith Clinic"]


async def test_update_facility_replaces_attributes(
    client: AsyncClient, system_admin_headers: dict[str, str], make_user: MakeUser
) -> None:
    created = (
        await client.post("/api/v1/facilities", json=_PAYLOAD, headers=system_admin_headers)
    ).json()
    _, admin_headers = await make_user(Role.FACILITY_ADMINISTRATOR, facility_id=created["id"])

    updated = await client.put(
        f"/api/v1/facilities/{created['id']}",
        json={**_PAYLOAD, "tier": "secondary", "contact_phone": "+233000000000"},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["tier"] == "secondary"
    assert updated.json()["contact_phone"] == "+233000000000"


async def test_update_facility_cross_facility_is_403(
    client: AsyncClient, system_admin_headers: dict[str, str], make_user: MakeUser
) -> None:
    created = (
        await client.post("/api/v1/facilities", json=_PAYLOAD, headers=system_admin_headers)
    ).json()
    other = (
        await client.post(
            "/api/v1/facilities", json={**_PAYLOAD, "name": "Other Clinic"},
            headers=system_admin_headers,
        )
    ).json()
    # An admin of `other` must not be able to edit `created` (FR17).
    _, other_admin_headers = await make_user(Role.FACILITY_ADMINISTRATOR, facility_id=other["id"])

    response = await client.put(
        f"/api/v1/facilities/{created['id']}", json=_PAYLOAD, headers=other_admin_headers
    )
    assert response.status_code == 403


async def test_patch_beds_upserts_count(
    client: AsyncClient, system_admin_headers: dict[str, str], make_user: MakeUser
) -> None:
    created = (
        await client.post("/api/v1/facilities", json=_PAYLOAD, headers=system_admin_headers)
    ).json()
    facility_id = created["id"]
    _, staff_headers = await make_user(Role.FACILITY_STAFF, facility_id=facility_id)

    inserted = await client.patch(
        f"/api/v1/facilities/{facility_id}/beds",
        json={"bed_type": "icu", "available": 3, "capacity": 12},
        headers=staff_headers,
    )
    assert inserted.status_code == 200
    icu = [b for b in inserted.json()["bed_counts"] if b["bed_type"] == "icu"]
    assert len(icu) == 1
    assert icu[0]["available"] == 3
    assert icu[0]["capacity"] == 12

    # Same bed_type again updates in place rather than inserting a second row.
    updated = await client.patch(
        f"/api/v1/facilities/{facility_id}/beds",
        json={"bed_type": "icu", "available": 1, "capacity": 12},
        headers=staff_headers,
    )
    icu_rows = [b for b in updated.json()["bed_counts"] if b["bed_type"] == "icu"]
    assert len(icu_rows) == 1
    assert icu_rows[0]["available"] == 1


async def test_patch_beds_as_dispatcher_is_403(
    client: AsyncClient, system_admin_headers: dict[str, str], dispatcher_headers: dict[str, str]
) -> None:
    """FR18: a dispatcher must never be able to write bed availability."""
    created = (
        await client.post("/api/v1/facilities", json=_PAYLOAD, headers=system_admin_headers)
    ).json()
    response = await client.patch(
        f"/api/v1/facilities/{created['id']}/beds",
        json={"bed_type": "icu", "available": 3, "capacity": 12},
        headers=dispatcher_headers,
    )
    assert response.status_code == 403


async def test_patch_beds_rejects_available_over_capacity(
    client: AsyncClient, system_admin_headers: dict[str, str], make_user: MakeUser
) -> None:
    created = (
        await client.post("/api/v1/facilities", json=_PAYLOAD, headers=system_admin_headers)
    ).json()
    _, staff_headers = await make_user(Role.FACILITY_STAFF, facility_id=created["id"])
    response = await client.patch(
        f"/api/v1/facilities/{created['id']}/beds",
        json={"bed_type": "icu", "available": 20, "capacity": 12},
        headers=staff_headers,
    )
    assert response.status_code == 422  # docs/02 §4 invariant: available <= capacity


async def test_create_rejects_empty_supported_bed_types(
    client: AsyncClient, system_admin_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/facilities",
        json={**_PAYLOAD, "supported_bed_types": []},
        headers=system_admin_headers,
    )
    assert response.status_code == 422


async def test_seed_loads_24_facilities(
    client: AsyncClient, system_admin_headers: dict[str, str]
) -> None:
    """RB-2: seeding yields 24 facilities, each with tier, bed types, and capacity."""
    run_seed_script()
    response = await client.get("/api/v1/facilities", headers=system_admin_headers)
    assert response.status_code == 200
    facilities = response.json()
    assert len(facilities) == 24

    for facility in facilities:
        assert facility["tier"] in {"tertiary", "secondary", "primary"}
        assert facility["supported_bed_types"]
        assert facility["bed_counts"]
        for bed in facility["bed_counts"]:
            assert bed["capacity"] >= 1

    # Re-running is idempotent (upsert by name): still exactly 24.
    run_seed_script()
    assert len((await client.get("/api/v1/facilities", headers=system_admin_headers)).json()) == 24
