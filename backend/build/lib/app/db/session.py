"""Async database engine, session factory, and readiness probe (docs/02-data-model.md).

The engine targets PostgreSQL 16 over asyncpg. ``get_session`` is the FastAPI dependency
that yields a request-scoped ``AsyncSession``; ``check_database_ready`` backs the
``/readyz`` endpoint (docs/04-api-spec.md §2) by issuing a trivial round-trip to the DB.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

# One engine per process. `pool_pre_ping` recycles connections that the DB dropped while
# idle, which matters because the engine container may outlive transient `db` restarts.
settings = get_settings()

database_url = settings.database_url

if database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+asyncpg://",
        1,
    )

_engine: AsyncEngine = create_async_engine(
    database_url,
    pool_pre_ping=True,
)

_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=_engine,
    expire_on_commit=False,
)


def get_engine() -> AsyncEngine:
    """Return the process-wide async engine (used by Alembic and for disposal at shutdown)."""
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide async session factory (used by ops scripts, e.g. seeding)."""
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped async session, ensuring it is closed afterwards.

    Used as a FastAPI dependency: ``session: AsyncSession = Depends(get_session)``.
    """
    async with _session_factory() as session:
        yield session


async def check_database_ready() -> bool:
    """Return True if the database answers a ``SELECT 1`` round-trip.

    Backs ``/readyz``: readiness means the DB is reachable, not merely that the process is
    up. Connection/operational failures are caught and reported as "not ready" rather than
    raised, so the readiness probe degrades cleanly instead of returning a 500.
    """
    try:
        async with _engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - any DB connectivity failure means "not ready".
        return False
