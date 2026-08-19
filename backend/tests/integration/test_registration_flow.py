"""Facility registration -> approval flow (docs/02 §2.4, FR16).

A pending request carries no privilege at all — there is no account to log into and no
facility to see. Approval, atomically, creates the facility and its first
facility_administrator; that new admin can immediately log in and act on their facility.
"""

from __future__ import annotations

from httpx import AsyncClient

_REQUEST_BODY = {
    "facility_name": "Ridge Community Clinic",
    "ghs_code": "GHS-RIDGE-01",
    "tier": "primary",
    "contact_email": "ridge-clinic@example.test",
    "contact_phone": "+233200000000",
}
_APPROVE_BODY = {
    "latitude": 5.58,
    "longitude": -0.19,
    "supported_bed_types": ["general", "maternity_specialist"],
    "initial_admin_email": "ridge-admin@example.test",
    "initial_admin_password": "a-strong-password-12",
}


async def test_submit_registration_requires_no_auth(client: AsyncClient) -> None:
    response = await client.post("/api/v1/registrations", json=_REQUEST_BODY)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["reviewed_by"] is None


async def test_pending_request_grants_no_login(client: AsyncClient) -> None:
    """A pending request creates no account — logging in as its contact confirms nothing exists."""
    await client.post("/api/v1/registrations", json=_REQUEST_BODY)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": _REQUEST_BODY["contact_email"], "password": "anything-at-all-123"},
    )
    assert response.status_code == 401


async def test_approval_creates_facility_and_working_admin_login(
    client: AsyncClient, system_admin_headers: dict[str, str]
) -> None:
    submitted = await client.post("/api/v1/registrations", json=_REQUEST_BODY)
    request_id = submitted.json()["id"]

    approved = await client.post(
        f"/api/v1/registrations/{request_id}/approve",
        json=_APPROVE_BODY,
        headers=system_admin_headers,
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["facility_name"] == _REQUEST_BODY["facility_name"]
    assert body["admin_email"] == _APPROVE_BODY["initial_admin_email"]

    # The facility is now readable.
    facility = await client.get(
        f"/api/v1/facilities/{body['facility_id']}", headers=system_admin_headers
    )
    assert facility.status_code == 200
    assert facility.json()["tier"] == "primary"

    # The new admin can log in and gets facility-scoped tokens.
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": _APPROVE_BODY["initial_admin_email"],
            "password": _APPROVE_BODY["initial_admin_password"],
        },
    )
    assert login.status_code == 200
    login_body = login.json()
    assert login_body["role"] == "facility_administrator"
    assert login_body["facility_id"] == body["facility_id"]

    # And can immediately act on their own facility.
    admin_headers = {"Authorization": f"Bearer {login_body['access_token']}"}
    update = await client.put(
        f"/api/v1/facilities/{body['facility_id']}",
        json={
            "name": _REQUEST_BODY["facility_name"],
            "latitude": _APPROVE_BODY["latitude"],
            "longitude": _APPROVE_BODY["longitude"],
            "tier": "primary",
            "supported_bed_types": _APPROVE_BODY["supported_bed_types"],
            "contact_phone": "+233200000001",
        },
        headers=admin_headers,
    )
    assert update.status_code == 200

    # The request itself is now approved, attributed to the reviewer.
    listed = await client.get(
        "/api/v1/registrations", params={"status": "approved"}, headers=system_admin_headers
    )
    assert len(listed.json()) == 1
    assert listed.json()[0]["reviewed_by"] is not None


async def test_reject_records_reason_and_status(
    client: AsyncClient, system_admin_headers: dict[str, str]
) -> None:
    submitted = await client.post("/api/v1/registrations", json=_REQUEST_BODY)
    request_id = submitted.json()["id"]

    rejected = await client.post(
        f"/api/v1/registrations/{request_id}/reject",
        json={"reason": "GHS code could not be verified"},
        headers=system_admin_headers,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["rejection_reason"] == "GHS code could not be verified"


async def test_approving_an_already_reviewed_request_is_409(
    client: AsyncClient, system_admin_headers: dict[str, str]
) -> None:
    submitted = await client.post("/api/v1/registrations", json=_REQUEST_BODY)
    request_id = submitted.json()["id"]
    await client.post(
        f"/api/v1/registrations/{request_id}/reject",
        json={"reason": "not eligible"},
        headers=system_admin_headers,
    )
    second = await client.post(
        f"/api/v1/registrations/{request_id}/approve",
        json=_APPROVE_BODY,
        headers=system_admin_headers,
    )
    assert second.status_code == 409


async def test_approving_unknown_request_is_404(
    client: AsyncClient, system_admin_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/registrations/00000000-0000-0000-0000-000000000000/approve",
        json=_APPROVE_BODY,
        headers=system_admin_headers,
    )
    assert response.status_code == 404
