"""``simulation_bed_state`` — isolated per-session bed availability (docs/02 §2.5).

One row per (session, facility, bed_type). This is the ONLY bed table a simulation run
reads or writes (docs/02 §4 invariant); ``bed_count`` and ``facility`` stay read-only during
a run. ``SimulationDataSource`` reads ``available`` here and decrements it on allocation.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import pg_enum
from app.parameters import BedType

if TYPE_CHECKING:
    from app.db.models.simulation_session import SimulationSession


class SimulationBedState(Base):
    """Seeded, per-session bed availability for one facility + bed type (docs/02 §2.5)."""

    __tablename__ = "simulation_bed_state"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "facility_id",
            "bed_type",
            name="uq_sim_bed_state_session_facility_bedtype",
        ),
        # Same availability invariants as bed_count (docs/02 §4); available == 0 at 100% occupancy.
        CheckConstraint("available >= 0", name="ck_sim_bed_state_available_nonneg"),
        CheckConstraint("available <= capacity", name="ck_sim_bed_state_available_le_capacity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulation_session.id", ondelete="CASCADE"),
        nullable=False,
    )
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facility.id", ondelete="CASCADE"), nullable=False
    )
    bed_type: Mapped[BedType] = mapped_column(pg_enum(BedType, "bedtype"), nullable=False)
    available: Mapped[int] = mapped_column(Integer, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    session: Mapped[SimulationSession] = relationship(back_populates="bed_states")
