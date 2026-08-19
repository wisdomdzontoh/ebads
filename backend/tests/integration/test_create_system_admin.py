"""``scripts/create_system_admin.py`` — the one out-of-band account-creation path (docs/02 §2.3).

Verifies the bootstrap script actually produces a working login, is idempotent by default,
and only resets a password when ``--force`` is passed. Run as a subprocess (like the facility
seed script) so it targets ``ebads_test``, not the settings-derived default database — its
internals never go through the FastAPI dependency override the ``client`` fixture uses.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.integration.conftest import run_create_system_admin, run_create_system_admin_env

# Not .test/.invalid/.localhost: those TLDs are special-use/reserved and EmailStr (via
# email-validator) rejects them outright, so a login through the real endpoint below would
# 422 rather than exercise the bootstrap flow this test is actually about.
_EMAIL = "root-admin@example.com"


async def test_bootstrap_creates_a_working_login(client: AsyncClient) -> None:
    run_create_system_admin(_EMAIL, "a-strong-password-12")

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": _EMAIL, "password": "a-strong-password-12"},
    )
    assert login.status_code == 200
    assert login.json()["role"] == "system_administrator"


async def test_bootstrap_is_a_no_op_without_force(client: AsyncClient) -> None:
    run_create_system_admin(_EMAIL, "a-strong-password-12")
    run_create_system_admin(_EMAIL, "a-different-password-99")

    # The original password still works — the second run did not overwrite it.
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": _EMAIL, "password": "a-strong-password-12"},
    )
    assert login.status_code == 200


async def test_bootstrap_force_resets_the_password(client: AsyncClient) -> None:
    run_create_system_admin(_EMAIL, "a-strong-password-12")
    run_create_system_admin(_EMAIL, "a-different-password-99", force=True)

    old_password = await client.post(
        "/api/v1/auth/login",
        json={"email": _EMAIL, "password": "a-strong-password-12"},
    )
    assert old_password.status_code == 401

    new_password = await client.post(
        "/api/v1/auth/login",
        json={"email": _EMAIL, "password": "a-different-password-99"},
    )
    assert new_password.status_code == 200


# The env-var-driven path below is what backend/Dockerfile's CMD runs unconditionally on
# every container start, for platforms with no shell/exec access (Render's free tier) — see
# scripts/create_system_admin.py's module docstring and DEPLOYMENT.md.

_SEED_EMAIL = "seed-admin@example.com"


async def test_seed_env_is_a_noop_when_unset(client: AsyncClient) -> None:
    result = run_create_system_admin_env(check=False)

    assert result.returncode == 0
    assert "skipping" in result.stdout

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": _SEED_EMAIL, "password": "irrelevant-not-created"},
    )
    assert login.status_code == 401


async def test_seed_env_creates_account_when_set(client: AsyncClient) -> None:
    result = run_create_system_admin_env(
        {"SEED_ADMIN_EMAIL": _SEED_EMAIL, "SEED_ADMIN_PASSWORD": "a-strong-password-12"}
    )

    assert result.returncode == 0
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": _SEED_EMAIL, "password": "a-strong-password-12"},
    )
    assert login.status_code == 200
    assert login.json()["role"] == "system_administrator"


async def test_seed_env_never_resets_an_existing_password(client: AsyncClient) -> None:
    """Redeploying with the same SEED_ADMIN_* values must not clobber a password rotated
    through any other path in the meantime (docstring: no --force in the automated path)."""
    run_create_system_admin(_SEED_EMAIL, "original-password-12")

    result = run_create_system_admin_env(
        {"SEED_ADMIN_EMAIL": _SEED_EMAIL, "SEED_ADMIN_PASSWORD": "a-different-password-99"}
    )

    assert result.returncode == 0
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": _SEED_EMAIL, "password": "original-password-12"},
    )
    assert login.status_code == 200


async def test_seed_env_fails_when_only_email_is_set(client: AsyncClient) -> None:
    result = run_create_system_admin_env({"SEED_ADMIN_EMAIL": _SEED_EMAIL}, check=False)

    assert result.returncode != 0
    assert "SEED_ADMIN_PASSWORD" in result.stderr


async def test_seed_env_fails_on_a_reserved_domain(client: AsyncClient) -> None:
    result = run_create_system_admin_env(
        {"SEED_ADMIN_EMAIL": "admin@example.test", "SEED_ADMIN_PASSWORD": "a-strong-password-12"},
        check=False,
    )

    assert result.returncode != 0
    assert "invalid email address" in result.stderr
