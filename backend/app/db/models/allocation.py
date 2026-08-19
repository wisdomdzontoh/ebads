"""``allocation`` — the decision made about one request (docs/02-data-model.md §3.5).

Persists everything ``AllocationService.allocate`` decides: which strategy ran, the weight
vector actually applied, the winning facility (null on escalation), and the reservation
attempt count (FR9 — how many candidates were tried before one succeeded, or all of them on
a race-exhausted escalation). ``status`` tracks the reservation lifecycle onward from here —
``domain/reservation/manager.py`` sets it to ``confirmed`` on a successful CAS reserve, the
expiry sweeper to ``expired``, ``POST .../arrive`` to ``arrived``, ``POST .../refuse`` to
``refused``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import pg_enum
from app.parameters import AlgorithmName, AllocationStatus

if TYPE_CHECKING:
    from app.db.models.emergency_request import EmergencyRequest


class Allocation(Base):
    """The decision for one ``emergency_request`` (docs/02-data-model.md §3.5)."""

    __tablename__ = "allocation"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emergency_request.id", ondelete="CASCADE"), nullable=False
    )
    # Null on escalation — no facility was committed.
    facility_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facility.id", ondelete="SET NULL"), nullable=True
    )
    strategy_used: Mapped[AlgorithmName] = mapped_column(
        pg_enum(AlgorithmName, "algorithm"), nullable=False
    )
    # The (w_t, w_b, w_c) actually applied; null for greedy / escalation (no scoring).
    weight_vector: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    travel_time_minutes: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    is_estimated_travel_time: Mapped[bool] = mapped_column(nullable=False, default=False)
    eta_minutes: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    capability_match: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    candidates_evaluated: Mapped[int] = mapped_column(Integer, nullable=False)
    # Reservation attempts before success, or before exhausting every candidate (FR9).
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selection_reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AllocationStatus] = mapped_column(
        pg_enum(AllocationStatus, "allocation_status"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # joined: every read of an allocation needs its request's facts (patient location,
    # urgency, dispatcher) in the same query — see api/routes/allocations.py.
    request: Mapped[EmergencyRequest] = relationship(lazy="joined")
