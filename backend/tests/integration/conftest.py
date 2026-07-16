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

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import normalize_database_url
from app.db.session import get_session
from app.main import create_app

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


# Clears every table; CASCADE handles the FK chains. Order is irrelevant with CASCADE.
_TRUNCATE = text(
    "TRUNCATE TABLE simulation_allocation_event, emergency_request, simulation_bed_state, "
    "simulation_session, bed_count, facility RESTART IDENTITY CASCADE"
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
