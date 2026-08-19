"""Integration-test harness: a real PostgreSQL database (docs/12-testing.md §7).

These tests run against an actual ``ebads_test`` database so the native enum types, the
array-of-enum column, and the migration itself are all exercised — none of which SQLite
could stand in for. The session fixture (1) recreates ``ebads_test`` and (2) applies the
real Alembic migration, so a broken migration fails the suite. Each test gets a clean schema
(tables truncated) and an httpx client whose DB session is overridden onto ``ebads_test``.

Requires a reachable Postgres (the docker-compose ``db`` locally, or the CI postgres
service). Override the target with ``TEST_DATABASE_URL``.
"""

from __future__ import annotations

import os

# A fixed, non-secret test signing key — app/security/jwt.py fails closed if this is unset
# (docs/09 §10). Settings.jwt_secret_key is read once into an @lru_cache'd singleton
# (app/config.py::get_settings), so this MUST run before any import below — several of them
# transitively import app.db.session, which calls get_settings() at module load time to
# build the DB engine, caching the (otherwise blank) settings before a later env-var write
# could take effect.
os.environ.setdefault("JWT_SECRET_KEY", "test-only-jwt-secret-key-at-least-32-bytes-long")

import asyncio
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from urllib.parse import urlparse

import email_validator
import psycopg
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Pydantic's EmailStr performs a real deliverability check by default (MX lookup /
# reserved-domain rejection), which fails every fixture email in this suite
# ("...@example.test" etc. — the RFC 2606 domains reserved exactly for this purpose).
# email_validator's own escape hatch for test suites is this flag, not a config option
# on our side — see https://github.com/JoshData/python-email-validator#testing.
email_validator.TEST_ENVIRONMENT = True

from app.config import normalize_database_url  # noqa: E402
from app.db.models.role import Role as RoleRow  # noqa: E402
from app.db.models.user_account import UserAccount  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import create_app  # noqa: E402
from app.parameters import Role  # noqa: E402
from app.security.jwt import create_access_token  # noqa: E402
from app.security.passwords import hash_password  # noqa: E402

# backend/ directory — used as cwd for the Alembic/seed subprocesses.
BACKEND_DIR = Path(__file__).resolve().parents[2]

# Normalized like DATABASE_URL, so any provider/driver spelling of the URL works here too.
TEST_DATABASE_URL = normalize_database_url(
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://ebads:ebads@localhost:5432/ebads_test",
    )
)


def _admin_connect_kwargs() -> tuple[dict[str, object], str]:
    """Split TEST_DATABASE_URL into psycopg connect kwargs and the target database name."""
    parsed = urlparse(TEST_DATABASE_URL.replace("+psycopg", ""))
    kwargs: dict[str, object] = {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "user": parsed.username,
        "password": parsed.password,
    }
    return kwargs, parsed.path.lstrip("/")


async def _recreate_database() -> None:
    """Drop and recreate the test database (CREATE DATABASE cannot run in a transaction)."""
    kwargs, dbname = _admin_connect_kwargs()
    # autocommit: CREATE/DROP DATABASE must run outside psycopg's implicit transaction.
    connection = await psycopg.AsyncConnection.connect(
        dbname="postgres", autocommit=True, **kwargs
    )
    try:
        await connection.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
        await connection.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        await connection.close()


def _run(args: list[str]) -> None:
    """Run a subprocess against the test database, raising on non-zero exit."""
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    subprocess.run(args, cwd=BACKEND_DIR, env=env, check=True)


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    """Recreate ``ebads_test`` and apply the real migration once per test session."""
    asyncio.run(_recreate_database())
    _run([sys.executable, "-m", "alembic", "upgrade", "head"])


def run_seed_script() -> None:
    """Run the facility seed script against the test database (for the RB-2 test)."""
    _run([sys.executable, "-m", "scripts.seed_facilities", "--source", "data/ga_facilities.csv"])


def run_create_system_admin(email: str, password: str, force: bool = False) -> None:
    """Run the system_administrator bootstrap script against the test database."""
    args = [
        sys.executable,
        "-m",
        "scripts.create_system_admin",
        "--email",
        email,
        "--password",
        password,
    ]
    if force:
        args.append("--force")
    _run(args)


# Clears every table; CASCADE handles the FK chains. Order is irrelevant with CASCADE.
# role/permission are deliberately NOT truncated — they are seeded once by migration 0005
# (docs/02 §6: "behaviour, not sample data"), not per-test fixture data.
_TRUNCATE = text(
    "TRUNCATE TABLE audit_log, facility_request, simulation_allocation_event, "
    "emergency_request, simulation_bed_state, simulation_session, bed_count, "
    "user_account, facility RESTART IDENTITY CASCADE"
)


@pytest_asyncio.fixture
async def app_under_test() -> AsyncIterator[FastAPI]:
    """Yield the FastAPI app bound to a freshly truncated ``ebads_test`` schema.

    Exposed so tests can override extra dependencies (e.g. the travel-time service).
    """
    engine = create_async_engine(TEST_DATABASE_URL)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.execute(_TRUNCATE)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = _override_session
    yield app
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(app_under_test: FastAPI) -> AsyncIterator[AsyncClient]:
    """Yield an httpx client driving the app under test."""
    transport = ASGITransport(app=app_under_test)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Yield a raw async session on a freshly truncated schema (for domain-layer tests)."""
    engine = create_async_engine(TEST_DATABASE_URL)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.execute(_TRUNCATE)

    async with sessionmaker() as session:
        yield session
    await engine.dispose()


# --- auth helpers (Increment 1: registry hardening + auth + RBAC) --------------------

MakeUser = Callable[..., Awaitable[tuple[UserAccount, dict[str, str]]]]


@pytest_asyncio.fixture
async def make_user(app_under_test: FastAPI) -> AsyncIterator[MakeUser]:
    """Factory fixture: create a ``user_account`` directly and return ``(user, headers)``.

    Depends on ``app_under_test`` so the schema-truncate has already run. Bypasses the
    ``/auth/login`` HTTP round-trip — tests exercise the RBAC boundary itself, not login,
    so minting the token directly (same code path as ``AuthService.login``) keeps them fast
    and focused. ``role`` rows come from migration 0005's seed; ``facility_id`` is required
    for facility_administrator/facility_staff, forbidden otherwise (docs/02 §2.3).
    """
    engine = create_async_engine(TEST_DATABASE_URL)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def _make(
        role: Role,
        *,
        facility_id: uuid.UUID | None = None,
        email: str | None = None,
    ) -> tuple[UserAccount, dict[str, str]]:
        async with sessionmaker() as session:
            role_row = await session.scalar(select(RoleRow).where(RoleRow.name == role))
            assert role_row is not None, f"role {role!r} is not seeded"
            user = UserAccount(
                email=email or f"{role.value}-{uuid.uuid4().hex[:8]}@example.test",
                password_hash=hash_password("test-password-123"),
                role_id=role_row.id,
                facility_id=facility_id,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        token = create_access_token(user.id, role, facility_id)
        return user, {"Authorization": f"Bearer {token}"}

    yield _make
    await engine.dispose()


@pytest_asyncio.fixture
async def system_admin_headers(make_user: MakeUser) -> dict[str, str]:
    """Bearer headers for a fresh system_administrator (the common case for most tests)."""
    _, headers = await make_user(Role.SYSTEM_ADMINISTRATOR)
    return headers


@pytest_asyncio.fixture
async def dispatcher_headers(make_user: MakeUser) -> dict[str, str]:
    """Bearer headers for a fresh dispatcher (the common case for allocation tests)."""
    _, headers = await make_user(Role.DISPATCHER)
    return headers
