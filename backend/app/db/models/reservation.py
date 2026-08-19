"""``reservation`` — the held bed's own lifetime (docs/02-data-model.md §3.6).

Separate from ``allocation`` because it has its own lifetime and can expire independently of
the allocation record (docs/02 §3.6: "Separate entity, not a column on allocation"). Created
only after a successful compare-and-set (``domain/reservation/manager.py``); released by the
expiry sweeper (``domain/sweeper/service.py``) or superseded by arrival (FR22) — whichever
happens first.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import pg_enum
from app.parameters import BedType


class Reservation(Base):
    """The held-bed record for one confirmed allocation (docs/02-data-model.md §3.6)."""

    __tablename__ = "reservation"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    allocation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("allocation.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facility.id", ondelete="CASCADE"), nullable=False
    )
    bed_type: Mapped[BedType] = mapped_column(pg_enum(BedType, "bedtype"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Advisory only — never blocks anything (FR20, docs/02 §3.6).
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # True once arrival is recorded (docs/02 §3.6) — NOT "reservation successfully created";
    # see domain/reservation/manager.py's module docstring for why these are kept distinct.
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Set by the expiry sweeper; also the sweeper's WHERE-clause guard against re-processing.
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
