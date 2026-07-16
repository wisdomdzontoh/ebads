"""``simulation_session`` — one isolated discrete-event simulation run (docs/02 §2.4).

A session fixes which algorithm runs, the occupancy scenario, the (optional) sensitivity
overrides, the seed, and how many events are planned. Its bed availability is held
separately in ``simulation_bed_state``, isolated per session so a run never touches the live
registry (docs/02 §4 invariant). The full event lifecycle (clock, LOS, metrics) arrives in
Phase 4; this model exists now because ``SimulationDataSource`` needs a session to scope
bed state to (docs/01 §3.2).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import pg_enum
from app.parameters import AlgorithmName

if TYPE_CHECKING:
    from app.db.models.simulation_bed_state import SimulationBedState


class SimulationSession(Base):
    """Configuration + identity of one simulation run (docs/02-data-model.md §2.4)."""

    __tablename__ = "simulation_session"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    algorithm_config: Mapped[AlgorithmName] = mapped_column(
        pg_enum(AlgorithmName, "algorithm"), nullable=False
    )
    # 0.75 / 0.90 / 1.00 — validated against parameters.OCCUPANCY_SCENARIOS at the API layer.
    occupancy_scenario: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    # Sensitivity overrides; null means "use the parameters.py defaults" (docs/02 §2.4).
    weight_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    radius_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    capability_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    random_seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    events_planned: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    bed_states: Mapped[list[SimulationBedState]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
