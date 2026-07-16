"""Alembic migration environment — async (docs/11-development-setup.md §4).

Reads the connection string from ``app.config.Settings`` (single source for DATABASE_URL)
and targets ``Base.metadata`` so ``alembic revision --autogenerate`` discovers every model
under ``app/db/models/``. Models are imported for their registration side effect; with no
models yet (Phase 0) the metadata is empty and ``upgrade head`` is a clean no-op.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

# Importing the models package registers every model on Base.metadata for autogenerate.
import app.db.models  # noqa: F401
from app.config import get_settings
from app.db.base import Base

config = context.config

# Inject the runtime database URL so it is never duplicated in alembic.ini.
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL without a live DB connection (``alembic upgrade --sql``)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    """Configure Alembic against an open connection and run the pending migrations."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Open an async engine and apply migrations within a real connection."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
