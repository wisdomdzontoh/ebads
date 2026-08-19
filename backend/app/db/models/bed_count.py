"""``bed_count`` — live bed availability for non-simulation data sources (docs/02 §3.2).

One row per (facility, bed_type) holds how many beds of that type are currently available
and the total capacity. This is the live registry state updated via
``PATCH /facilities/{id}/beds`` (human writes, ``updated_by`` set) or a ``BedDataSource``
adapter's ``reserve``/``release`` (``updated_by`` left null — docs/02 §3.2). Simulation runs
do NOT use this table — they keep isolated per-session state in ``simulation_bed_state``
(docs/02 §4 invariant).

**``version`` is the concurrency mechanism (docs/02 §3.2).** Every write to ``available``
increments it in the same statement — never update one without the other. It is what makes
``ManualAdapter.reserve`` (``domain/beds/manual_adapter.py``) an atomic compare-and-set
rather than a read-then-write race.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import pg_enum
from app.parameters import BedType

if TYPE_CHECKING:
    from app.db.models.facility import Facility


class BedCount(Base):
    """Available/total beds of one type at one facility (docs/02-data-model.md §3.2)."""

    __tablename__ = "bed_count"
    __table_args__ = (
        # docs/02 §3: bed_count(facility_id, bed_type) is unique.
        UniqueConstraint("facility_id", "bed_type", name="uq_bed_count_facility_bedtype"),
        # docs/02 §4 invariants: available >= 0 and available <= capacity, enforced at the DB.
        CheckConstraint("available >= 0", name="ck_bed_count_available_nonneg"),
        CheckConstraint("available <= capacity", name="ck_bed_count_available_le_capacity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facility.id", ondelete="CASCADE"), nullable=False
    )
    bed_type: Mapped[BedType] = mapped_column(pg_enum(BedType, "bedtype"), nullable=False)
    available: Mapped[int] = mapped_column(Integer, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    # Compare-and-set concurrency token (docs/02 §3.2) — see the module docstring.
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_account.id", ondelete="SET NULL"), nullable=True
    )

    facility: Mapped[Facility] = relationship(back_populates="bed_counts")
