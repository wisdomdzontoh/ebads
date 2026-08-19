"""``facility_request`` — registration request, carrying no privilege (docs/02 §2.4).

FR16: a pending request cannot authenticate anything — it is not a ``user_account`` and
grants no access. Approval (``domain/registry/service.py``) creates the ``facility`` row
and its first ``facility_administrator`` in one transaction; rejection just records why.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import pg_enum
from app.parameters import FacilityRequestStatus, Tier


class FacilityRequest(Base):
    """A pending/approved/rejected request to join the registry (docs/02-data-model.md §2.4)."""

    __tablename__ = "facility_request"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_name: Mapped[str] = mapped_column(Text, nullable=False)
    ghs_code: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[Tier] = mapped_column(pg_enum(Tier, "tier"), nullable=False)
    contact_email: Mapped[str] = mapped_column(Text, nullable=False)
    contact_phone: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[FacilityRequestStatus] = mapped_column(
        pg_enum(FacilityRequestStatus, "facility_request_status"),
        nullable=False,
        default=FacilityRequestStatus.PENDING,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_account.id"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
