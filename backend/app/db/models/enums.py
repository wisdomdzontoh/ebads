"""PostgreSQL native-enum column types for the ORM models (docs/02-data-model.md).

SQLAlchemy's ``Enum`` defaults to storing a Python enum's *member name* (e.g. ``CRITICAL``).
The data model and API use the lowercase *values* (e.g. ``critical``, ``tertiary``,
``general``, ``simulation``), so every enum column is built through ``pg_enum`` with a
``values_callable`` that emits the values. ``create_type=False`` because the Alembic
migration owns CREATE/DROP TYPE — the models reference the types, they do not create them.
"""

from __future__ import annotations

from enum import Enum

from sqlalchemy.dialects.postgresql import ENUM


def pg_enum(enum_cls: type[Enum], name: str) -> ENUM:
    """Return a PostgreSQL ENUM column type for ``enum_cls`` storing its lowercase values.

    Args:
        enum_cls: the Python enum whose values become the PG enum labels.
        name: the PostgreSQL type name (must match the name created in the migration).
    """
    return ENUM(
        enum_cls,
        name=name,
        values_callable=lambda e: [member.value for member in e],
        create_type=False,
    )
