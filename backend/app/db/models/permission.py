"""``permission`` — the RBAC matrix, seeded by migration (docs/02-data-model.md §2.2).

Permissions are data, not code: the RBAC dependency (``app/security/dependencies.py``)
reads this table at request time, so a permission change is a migration, not a deploy
(docs/01-architecture.md §4). Never written by application code at runtime.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import pg_enum
from app.parameters import PermissionAction, PermissionScope


class Permission(Base):
    """One (role, resource, action) grant, at a given scope (docs/02-data-model.md §2.2)."""

    __tablename__ = "permission"
    __table_args__ = (
        UniqueConstraint(
            "role_id", "resource", "action", name="uq_permission_role_resource_action"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("role.id", ondelete="CASCADE"), nullable=False
    )
    # e.g. "facility", "bed_state", "user_account", "facility_request", "allocation",
    # "config", "audit_log" (docs/02 §2.2). Free text, not an enum — the resource set is a
    # convention shared with app/security/dependencies.py, not a schema-level constraint.
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[PermissionAction] = mapped_column(
        pg_enum(PermissionAction, "permission_action"), nullable=False
    )
    scope: Mapped[PermissionScope] = mapped_column(
        pg_enum(PermissionScope, "permission_scope"), nullable=False
    )
