"""``emergency_request`` — audit of every allocation (docs/02-data-model.md §2.3).

One row per allocation request (live or simulation), recording the inputs, the algorithm and
weight vector actually applied, the recommendation (or escalation), and the search effort.
Auditability is a thesis requirement: the weight vector is persisted on every record so any
decision can be reconstructed. Escalated records have ``recommended_facility_id = null`` and
``status = escalated`` (docs/02 §4).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import pg_enum
from app.parameters import AlgorithmName, BedType, Status, Urgency


class EmergencyRequest(Base):
    """Persisted audit record for one allocation (docs/02-data-model.md §2.3)."""

    __tablename__ = "emergency_request"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    patient_lat: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    patient_lon: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    # null when urgency was missing/invalid (Algorithm 2 fallback applied).
    urgency: Mapped[Urgency | None] = mapped_column(pg_enum(Urgency, "urgency"), nullable=True)
    required_bed_type: Mapped[BedType] = mapped_column(pg_enum(BedType, "bedtype"), nullable=False)
    simulation_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulation_session.id", ondelete="SET NULL"),
        nullable=True,
    )
    algorithm_used: Mapped[AlgorithmName] = mapped_column(
        pg_enum(AlgorithmName, "algorithm"), nullable=False
    )
    # The (w_t, w_b, w_c) actually applied; null for greedy / escalation (no scoring).
    weight_vector: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    selection_reason: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_facility_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facility.id", ondelete="SET NULL"), nullable=True
    )
    travel_time_minutes: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    is_estimated_travel_time: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    capability_match: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    candidates_evaluated: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[Status] = mapped_column(pg_enum(Status, "status"), nullable=False, index=True)
