"""Every create/modify/approve is attributable to an authenticated account (NFR8)."""

from __future__ import annotations

from httpx import AsyncClient

from app.parameters import Role
from tests.integration.conftest import MakeUser

_FACILITY_BODY = {
    "name": "Audit Test Facility",
    "latitude": 5.60,
    "longitude": -0.20,
    "tier": "tertiary",
    "supported_bed_types": ["general"],
    "contact_phone": "+233000000000",
}


def _entries(body: list[dict[str, object]], entity: str, action: str) -> list[dict[str, object]]:
    return [e for e in body if e["entity"] == entity and e["action"] == action]


async def test_facility_create_is_audited(
    client: AsyncClient, system_admin_headers: dict[str, str]
) -> None:
    created = (
        await client.post("/api/v1/facilities", json=_FACILITY_BODY, headers=system_admin_headers)
    ).json()

    log = await client.get("/api/v1/audit-log", headers=system_admin_headers)
    assert log.status_code == 200
    matches = _entries(log.json(), "facility", "create")
    assert any(entry["entity_id"] == created["id"] for entry in matches)
    matched = next(entry for entry in matches if entry["entity_id"] == created["id"])
    assert matched["user_id"] is not None


async def test_bed_update_is_audited(
    client: AsyncClient, system_admin_headers: dict[str, str], make_user: MakeUser
) -> None:
    created = (
        await client.post("/api/v1/facilities", json=_FACILITY_BODY, headers=system_admin_headers)
    ).json()
    staff, staff_headers = await make_user(Role.FACILITY_STAFF, facility_id=created["id"])
    await client.patch(
        f"/api/v1/facilities/{created['id']}/beds",
        json={"bed_type": "general", "available": 2, "capacity": 5},
        headers=staff_headers,
    )

    log = await client.get("/api/v1/audit-log", headers=system_admin_headers)
    matches = _entries(log.json(), "bed_state", "update")
    matched = next(entry for entry in matches if entry["entity_id"] == created["id"])
    assert matched["user_id"] == str(staff.id)


async def test_login_is_audited(client: AsyncClient, make_user: MakeUser) -> None:
    user, _ = await make_user(Role.DISPATCHER, email="dispatcher@example.test")
    await client.post(
        "/api/v1/auth/login",
        json={"email": "dispatcher@example.test", "password": "test-password-123"},
    )
    # Read the log as a system_administrator created purely to inspect it.
    _, admin_headers = await make_user(Role.SYSTEM_ADMINISTRATOR)
    log = await client.get("/api/v1/audit-log", headers=admin_headers)
    matches = _entries(log.json(), "user_account", "login")
    assert any(entry["entity_id"] == str(user.id) for entry in matches)


async def test_registration_approval_audits_three_entities(
    client: AsyncClient, system_admin_headers: dict[str, str]
) -> None:
    submitted = await client.post(
        "/api/v1/registrations",
        json={
            "facility_name": "Audit Flow Clinic",
            "ghs_code": "GHS-AUDIT-01",
            "tier": "primary",
            "contact_email": "audit-clinic@example.test",
            "contact_phone": "+233200000000",
        },
    )
    request_id = submitted.json()["id"]
    approved = await client.post(
        f"/api/v1/registrations/{request_id}/approve",
        json={
            "latitude": 5.58,
            "longitude": -0.19,
            "supported_bed_types": ["general"],
            "initial_admin_email": "audit-admin@example.test",
            "initial_admin_password": "a-strong-password-12",
        },
        headers=system_admin_headers,
    )
    body = approved.json()

    log = (await client.get("/api/v1/audit-log", headers=system_admin_headers)).json()
    assert any(
        e["entity"] == "facility_request"
        and e["action"] == "approve"
        and e["entity_id"] == request_id
        for e in log
    )
    assert any(
        e["entity"] == "facility"
        and e["action"] == "create"
        and e["entity_id"] == body["facility_id"]
        for e in log
    )
    assert any(
        e["entity"] == "user_account"
        and e["action"] == "create"
        and e["entity_id"] == body["admin_user_id"]
        for e in log
    )


async def test_audit_log_is_system_administrator_only(
    client: AsyncClient, dispatcher_headers: dict[str, str]
) -> None:
    response = await client.get("/api/v1/audit-log", headers=dispatcher_headers)
    assert response.status_code == 403
