"""``decision_log`` — the replayable record of one scoring decision (docs/02 §3.8, FR12).

Every scored candidate (facility, t_hat, b_hat, c_hat, score) plus the weight vector and the
parameter snapshot in effect — enough that recomputing the score from ``candidates`` +
``weights`` reproduces the logged ranking exactly (FR12's accept criterion, NFR4).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DecisionLog(Base):
    """The full scored candidate set behind one allocation decision (docs/02-data-model.md §3.8)."""

    __tablename__ = "decision_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    allocation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("allocation.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # Every candidate with t_hat/b_hat/c_hat and score (FR12) — list[dict], not further typed
    # here; the shape is defined by domain/reservation/decision_log.py::build_candidates_json.
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    weights: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    parameters_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rejected_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
