"""POST /auth/login, POST /auth/refresh integration tests (EBADS_PRD.md §10, FR15)."""

from __future__ import annotations

from httpx import AsyncClient

from app.parameters import Role
from tests.integration.conftest import MakeUser


async def test_login_with_correct_password_returns_tokens(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user, _ = await make_user(Role.DISPATCHER, email="dispatcher@example.test")
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "dispatcher@example.test", "password": "test-password-123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["role"] == "dispatcher"
    assert body["facility_id"] is None


async def test_login_with_wrong_password_is_401(client: AsyncClient, make_user: MakeUser) -> None:
    await make_user(Role.DISPATCHER, email="dispatcher@example.test")
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "dispatcher@example.test", "password": "totally-wrong-password"},
    )
    assert response.status_code == 401


async def test_login_with_unknown_email_is_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.test", "password": "whatever-password-123"},
    )
    assert response.status_code == 401


async def test_access_token_authenticates_a_protected_route(
    client: AsyncClient, make_user: MakeUser
) -> None:
    await make_user(Role.DISPATCHER, email="dispatcher@example.test")
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "dispatcher@example.test", "password": "test-password-123"},
    )
    access_token = login.json()["access_token"]
    response = await client.get(
        "/api/v1/allocations", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200


async def test_refresh_returns_a_new_access_token(client: AsyncClient, make_user: MakeUser) -> None:
    await make_user(Role.DISPATCHER, email="dispatcher@example.test")
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "dispatcher@example.test", "password": "test-password-123"},
    )
    refresh_token = login.json()["refresh_token"]
    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]


async def test_refresh_rejects_an_access_token(client: AsyncClient, make_user: MakeUser) -> None:
    await make_user(Role.DISPATCHER, email="dispatcher@example.test")
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "dispatcher@example.test", "password": "test-password-123"},
    )
    access_token = login.json()["access_token"]
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert response.status_code == 401


async def test_garbage_refresh_token_is_401(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-token"})
    assert response.status_code == 401
