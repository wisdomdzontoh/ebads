"""``role`` — the four account roles, seeded by migration (docs/02-data-model.md §2.1).

Static, migration-seeded reference data (docs/02 §6: "behaviour, not sample data"). Never
inserted or edited at runtime by application code.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import pg_enum
from app.parameters import Role as RoleName


class Role(Base):
    """One of the four roles (docs/02-data-model.md §2.1)."""

    __tablename__ = "role"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[RoleName] = mapped_column(
        pg_enum(RoleName, "role_name"), nullable=False, unique=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
