"""Role x endpoint RBAC matrix (FR15, FR17, FR18; docs/01 §4, docs/AGENTS.md §3).

Complements the auth-specific assertions embedded in test_facilities.py/
test_allocations_api.py/test_simulation_api.py with a systematic sweep: every protected
endpoint 401s with no token, and a representative set of wrong-role calls 403 — proving
``require_permission`` is the single enforcement point rather than trusting per-endpoint
spot checks alone.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.parameters import Role
from tests.integration.conftest import MakeUser

_UNKNOWN = "00000000-0000-0000-0000-000000000000"

_VALID_FACILITY_BODY = {
    "name": "RBAC Matrix Facility",
    "latitude": 5.60,
    "longitude": -0.20,
    "tier": "tertiary",
    "supported_bed_types": ["general"],
    "contact_phone": "+233000000000",
}
_VALID_BED_BODY = {"bed_type": "general", "available": 1, "capacity": 1}
_VALID_ALLOCATION_BODY = {"patient_lat": 5.6, "patient_lon": -0.2, "required_bed_type": "general"}
_VALID_REGISTRATION_BODY = {
    "facility_name": "New Clinic",
    "ghs_code": "GHS-001",
    "tier": "primary",
    "contact_email": "clinic@example.test",
    "contact_phone": "+233000000000",
}
_VALID_APPROVE_BODY = {
    "latitude": 5.6,
    "longitude": -0.2,
    "supported_bed_types": ["general"],
    "initial_admin_email": "admin@example.test",
    "initial_admin_password": "a-strong-password-12",
}
_VALID_USER_BODY = {
    "email": "new-dispatcher@example.test",
    "password": "a-strong-password-12",
    "role": "dispatcher",
}

# (method, path, json_body) — a representative sweep, not every endpoint.
_PROTECTED_ENDPOINTS: list[tuple[str, str, dict[str, object] | None]] = [
    ("POST", "/api/v1/facilities", _VALID_FACILITY_BODY),
    ("GET", "/api/v1/facilities", None),
    ("PUT", f"/api/v1/facilities/{_UNKNOWN}", _VALID_FACILITY_BODY),
    ("PATCH", f"/api/v1/facilities/{_UNKNOWN}/beds", _VALID_BED_BODY),
    ("POST", "/api/v1/allocations", _VALID_ALLOCATION_BODY),
    ("GET", "/api/v1/allocations", None),
    ("GET", "/api/v1/registrations", None),
    ("POST", f"/api/v1/registrations/{_UNKNOWN}/approve", _VALID_APPROVE_BODY),
    ("POST", "/api/v1/users", _VALID_USER_BODY),
    ("GET", "/api/v1/users", None),
    ("GET", "/api/v1/audit-log", None),
    ("POST", "/api/v1/simulation/sessions", {"algorithm_config": "weighted",
        "occupancy_scenario": 0.75, "events_planned": 1, "random_seed": 1}),
]


@pytest.mark.parametrize("method,path,body", _PROTECTED_ENDPOINTS)
async def test_unauthenticated_request_is_401(
    client: AsyncClient, method: str, path: str, body: dict[str, object] | None
) -> None:
    response = await client.request(method, path, json=body)
    assert response.status_code == 401


async def test_dispatcher_cannot_write_bed_state(
    client: AsyncClient,
    system_admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    make_user: MakeUser,
) -> None:
    """FR18: a dispatcher must never write bed availability, on any facility."""
    created = (
        await client.post(
            "/api/v1/facilities", json=_VALID_FACILITY_BODY, headers=system_admin_headers
        )
    ).json()
    response = await client.patch(
        f"/api/v1/facilities/{created['id']}/beds",
        json=_VALID_BED_BODY,
        headers=dispatcher_headers,
    )
    assert response.status_code == 403


async def test_dispatcher_cannot_manage_users_or_read_audit_log(
    client: AsyncClient, dispatcher_headers: dict[str, str]
) -> None:
    for method, path, body in [
        ("POST", "/api/v1/users", _VALID_USER_BODY),
        ("GET", "/api/v1/users", None),
        ("GET", "/api/v1/audit-log", None),
        ("GET", "/api/v1/registrations", None),
    ]:
        response = await client.request(method, path, json=body, headers=dispatcher_headers)
        assert response.status_code == 403, f"{method} {path} should 403 for a dispatcher"


async def test_facility_staff_cannot_submit_allocations(
    client: AsyncClient, system_admin_headers: dict[str, str], make_user: MakeUser
) -> None:
    """The separation of duties in FR18 cuts both ways: staff cannot dispatch either."""
    created = (
        await client.post(
            "/api/v1/facilities", json=_VALID_FACILITY_BODY, headers=system_admin_headers
        )
    ).json()
    _, staff_headers = await make_user(Role.FACILITY_STAFF, facility_id=created["id"])
    response = await client.post(
        "/api/v1/allocations", json=_VALID_ALLOCATION_BODY, headers=staff_headers
    )
    assert response.status_code == 403


async def test_facility_administrator_cannot_approve_registrations(
    client: AsyncClient, system_admin_headers: dict[str, str], make_user: MakeUser
) -> None:
    """Approval is system_administrator only (FR16) — facility_administrator may not self-serve."""
    created = (
        await client.post(
            "/api/v1/facilities", json=_VALID_FACILITY_BODY, headers=system_admin_headers
        )
    ).json()
    _, admin_headers = await make_user(Role.FACILITY_ADMINISTRATOR, facility_id=created["id"])
    response = await client.post(
        f"/api/v1/registrations/{_UNKNOWN}/approve", json=_VALID_APPROVE_BODY, headers=admin_headers
    )
    assert response.status_code == 403


async def test_facility_administrator_new_user_is_pinned_to_own_facility(
    client: AsyncClient, system_admin_headers: dict[str, str], make_user: MakeUser
) -> None:
    """A facility_administrator cannot provision into a facility other than their own —

    the payload's ``facility_id`` is ignored, not merely validated (domain/users/service.py).
    """
    facility_a = (
        await client.post(
            "/api/v1/facilities", json={**_VALID_FACILITY_BODY, "name": "Facility A"},
            headers=system_admin_headers,
        )
    ).json()
    facility_b = (
        await client.post(
            "/api/v1/facilities", json={**_VALID_FACILITY_BODY, "name": "Facility B"},
            headers=system_admin_headers,
        )
    ).json()
    _, admin_a_headers = await make_user(Role.FACILITY_ADMINISTRATOR, facility_id=facility_a["id"])

    response = await client.post(
        "/api/v1/users",
        json={
            "email": "staff-a@example.test",
            "password": "a-strong-password-12",
            "role": "facility_staff",
            "facility_id": facility_b["id"],  # attempted cross-facility provisioning
        },
        headers=admin_a_headers,
    )
    assert response.status_code == 201
    assert response.json()["facility_id"] == facility_a["id"]  # pinned, not facility_b


async def test_facility_administrator_cannot_create_dispatcher(
    client: AsyncClient, system_admin_headers: dict[str, str], make_user: MakeUser
) -> None:
    created = (
        await client.post(
            "/api/v1/facilities", json=_VALID_FACILITY_BODY, headers=system_admin_headers
        )
    ).json()
    _, admin_headers = await make_user(Role.FACILITY_ADMINISTRATOR, facility_id=created["id"])
    response = await client.post(
        "/api/v1/users",
        json={"email": "x@example.test", "password": "a-strong-password-12", "role": "dispatcher"},
        headers=admin_headers,
    )
    assert response.status_code == 422
