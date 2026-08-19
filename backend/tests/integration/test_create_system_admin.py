"""``scripts/create_system_admin.py`` — the one out-of-band account-creation path (docs/02 §2.3).

Verifies the bootstrap script actually produces a working login, is idempotent by default,
and only resets a password when ``--force`` is passed. Run as a subprocess (like the facility
seed script) so it targets ``ebads_test``, not the settings-derived default database — its
internals never go through the FastAPI dependency override the ``client`` fixture uses.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.integration.conftest import run_create_system_admin


async def test_bootstrap_creates_a_working_login(client: AsyncClient) -> None:
    run_create_system_admin("root-admin@example.test", "a-strong-password-12")

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "root-admin@example.test", "password": "a-strong-password-12"},
    )
    assert login.status_code == 200
    assert login.json()["role"] == "system_administrator"


async def test_bootstrap_is_a_no_op_without_force(client: AsyncClient) -> None:
    run_create_system_admin("root-admin@example.test", "a-strong-password-12")
    run_create_system_admin("root-admin@example.test", "a-different-password-99")

    # The original password still works — the second run did not overwrite it.
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "root-admin@example.test", "password": "a-strong-password-12"},
    )
    assert login.status_code == 200


async def test_bootstrap_force_resets_the_password(client: AsyncClient) -> None:
    run_create_system_admin("root-admin@example.test", "a-strong-password-12")
    run_create_system_admin("root-admin@example.test", "a-different-password-99", force=True)

    old_password = await client.post(
        "/api/v1/auth/login",
        json={"email": "root-admin@example.test", "password": "a-strong-password-12"},
    )
    assert old_password.status_code == 401

    new_password = await client.post(
        "/api/v1/auth/login",
        json={"email": "root-admin@example.test", "password": "a-different-password-99"},
    )
    assert new_password.status_code == 200
