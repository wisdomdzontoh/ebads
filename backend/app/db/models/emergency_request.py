"""``emergency_request`` — what was asked (docs/02-data-model.md §3.4).

One row per submitted request (live only — simulation calls ``AllocationService.evaluate``
directly and persists its own ``simulation_allocation_event`` rows, never this table). Carries
only the request's own facts; the decision made about it lives in ``allocation`` (docs/02
§3.5), a separate entity so a request's fixed inputs are never conflated with an outcome that
can itself change lifecycle state over time (pending → confirmed → arrived/expired/refused).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import pg_enum
from app.parameters import BedType, Urgency


class EmergencyRequest(Base):
    """One dispatcher-submitted request (docs/02-data-model.md §3.4)."""

    __tablename__ = "emergency_request"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    # Nullable: only live requests submitted through the authenticated API carry a
    # dispatcher (docs/02 §3.4, NFR8). No other caller reaches this table (see module note).
    dispatcher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_account.id", ondelete="SET NULL"), nullable=True
    )
    patient_lat: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    patient_lon: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    # null when urgency was missing/invalid (fixed-weight fallback applied — docs/03 §8).
    urgency: Mapped[Urgency | None] = mapped_column(pg_enum(Urgency, "urgency"), nullable=True)
    required_bed_type: Mapped[BedType] = mapped_column(pg_enum(BedType, "bedtype"), nullable=False)
    simulation_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulation_session.id", ondelete="SET NULL"),
        nullable=True,
    )
