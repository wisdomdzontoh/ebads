"""``user_account`` — every authenticated principal (docs/02-data-model.md §2.3).

Exactly one role per account. ``facility_id`` is null for ``system_administrator`` and
``dispatcher`` (unscoped roles) and required for ``facility_administrator``/``facility_staff``
(facility-scoped roles). The doc calls this a CHECK constraint, but the check spans two
tables (it depends on ``role.name``, reached through ``role_id``), which a plain Postgres
CHECK cannot express — the migration enforces it with an equivalent trigger instead
(see ``20260818_0005_auth_rbac.py``). It is also validated in ``domain/users/service.py``
so a violation surfaces as a clear 422, not a raw DB error.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import pg_enum
from app.parameters import UserStatus

if TYPE_CHECKING:
    from app.db.models.role import Role


class UserAccount(Base):
    """An authenticated principal — dispatcher, facility staff/admin, or system admin."""

    __tablename__ = "user_account"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("role.id"), nullable=False
    )
    facility_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facility.id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[UserStatus] = mapped_column(
        pg_enum(UserStatus, "user_status"), nullable=False, default=UserStatus.ACTIVE
    )
    # No self-registration: every account has a creator (docs/02 §2.3). Null only for the
    # very first system_administrator, created out-of-band by a seed script/operator.
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_account.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # joined: the role name is needed on every authenticated request (RBAC dependency), so
    # load it in the same query rather than a lazy second round-trip.
    role: Mapped[Role] = relationship(lazy="joined")
