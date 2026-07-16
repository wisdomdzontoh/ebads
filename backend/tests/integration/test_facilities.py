"""Facility Registry CRUD + seed integration tests (docs/04 §3; Phase 1 acceptance).

Covers the happy paths and the documented error/invariant behaviour for the
``/facilities`` endpoints, plus RB-2: the seed script loads exactly 24 facilities, each with
a tier, supported bed types, and capacity.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.integration.conftest import run_seed_script

# A minimal valid facility payload reused across tests.
_PAYLOAD = {
    "name": "37 Military Hospital",
    "latitude": 5.5826,
    "longitude": -0.1880,
    "tier": "tertiary",
    "supported_bed_types": ["general", "icu", "maternity_specialist"],
    "contact_phone": "+233302776111",
    "active_data_source": "simulation",
}


async def test_create_then_get_facility(client: AsyncClient) -> None:
    created = await client.post("/api/v1/facilities", json=_PAYLOAD)
    assert created.status_code == 201
    body = created.json()
    assert body["id"]
    assert body["tier"] == "tertiary"
    assert body["bed_counts"] == []  # no beds until PATCH .../beds

    fetched = await client.get(f"/api/v1/facilities/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == _PAYLOAD["name"]


async def test_get_unknown_facility_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/facilities/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_list_facilities_sorted_by_name(client: AsyncClient) -> None:
    await client.post("/api/v1/facilities", json={**_PAYLOAD, "name": "Zenith Clinic"})
    await client.post("/api/v1/facilities", json={**_PAYLOAD, "name": "Alpha Clinic"})
    response = await client.get("/api/v1/facilities")
    assert response.status_code == 200
    names = [f["name"] for f in response.json()]
    assert names == ["Alpha Clinic", "Zenith Clinic"]


async def test_update_facility_replaces_attributes(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/facilities", json=_PAYLOAD)).json()
    updated = await client.put(
        f"/api/v1/facilities/{created['id']}",
        json={**_PAYLOAD, "tier": "secondary", "contact_phone": "+233000000000"},
    )
    assert updated.status_code == 200
    assert updated.json()["tier"] == "secondary"
    assert updated.json()["contact_phone"] == "+233000000000"


async def test_patch_beds_upserts_count(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/facilities", json=_PAYLOAD)).json()
    facility_id = created["id"]

    inserted = await client.patch(
        f"/api/v1/facilities/{facility_id}/beds",
        json={"bed_type": "icu", "available": 3, "capacity": 12},
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
    )
    icu_rows = [b for b in updated.json()["bed_counts"] if b["bed_type"] == "icu"]
    assert len(icu_rows) == 1
    assert icu_rows[0]["available"] == 1


async def test_patch_beds_rejects_available_over_capacity(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/facilities", json=_PAYLOAD)).json()
    response = await client.patch(
        f"/api/v1/facilities/{created['id']}/beds",
        json={"bed_type": "icu", "available": 20, "capacity": 12},
    )
    assert response.status_code == 422  # docs/02 §4 invariant: available <= capacity


async def test_create_rejects_empty_supported_bed_types(client: AsyncClient) -> None:
    response = await client.post("/api/v1/facilities", json={**_PAYLOAD, "supported_bed_types": []})
    assert response.status_code == 422


async def test_seed_loads_24_facilities(client: AsyncClient) -> None:
    """RB-2: seeding yields 24 facilities, each with tier, bed types, and capacity."""
    run_seed_script()
    response = await client.get("/api/v1/facilities")
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
    assert len((await client.get("/api/v1/facilities")).json()) == 24
