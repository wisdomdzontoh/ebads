"""SQLAlchemy declarative base (docs/02-data-model.md).

Every ORM model in ``app/db/models/`` subclasses ``Base`` so that Alembic's
autogenerate can discover the full schema from ``Base.metadata``. No models exist yet
(they arrive in Phase 1); this base is the anchor they will attach to.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base shared by all EBADS ORM models."""
