"""``simulation_allocation_event`` — one processed simulation event (docs/02 §2.6).

The simulation engine persists exactly one row per event it processes on the virtual clock:
the generated inputs (arrival time, urgency, bed type, patient location) and the decision
(recommendation or escalation, travel time, placement time, capability match, search effort).
These rows are the raw material the per-run metrics (ATBP, FRR, MCEE, CM — docs/07 §8) are
computed from, and re-deriving availability from them (allocated events still holding a bed
at time ``t``) is how the engine models bed release without any in-memory state.

Escalated events carry ``recommended_facility_id = null`` and null placement fields, matching
the ``emergency_request`` escalation shape (docs/02 §4). Only allocated events sample a
length of stay (``los_minutes``) and a ``bed_release_virtual_min`` = arrival + LOS.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import pg_enum
from app.parameters import BedType, Status, Urgency


class SimulationAllocationEvent(Base):
    """Per-event record produced by a simulation run (docs/02-data-model.md §2.6)."""

    __tablename__ = "simulation_allocation_event"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulation_session.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 0..events_planned-1; unique per session and the ordering key on the virtual clock.
    event_index: Mapped[int] = mapped_column(Integer, nullable=False)
    virtual_arrival_min: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    urgency: Mapped[Urgency] = mapped_column(pg_enum(Urgency, "urgency"), nullable=False)
    required_bed_type: Mapped[BedType] = mapped_column(pg_enum(BedType, "bedtype"), nullable=False)
    patient_lat: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    patient_lon: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    # Decision fields — all null on escalation (no facility placed).
    recommended_facility_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facility.id", ondelete="SET NULL"), nullable=True
    )
    travel_time_minutes: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    # Overhead + travel time (the ATBP contribution); not wall-clock latency (docs/07 §2).
    time_to_bed_placement_min: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    capability_match: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    candidates_evaluated: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[Status] = mapped_column(pg_enum(Status, "status"), nullable=False)
    # Sampled length of stay + when the bed returns to the pool (allocated events only).
    los_minutes: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    bed_release_virtual_min: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
