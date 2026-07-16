"""``facility`` — the static registry entity (docs/02-data-model.md §2.1).

A facility holds attributes that do not change moment-to-moment (location, capability tier,
the bed types it offers, contact details, and which BedDataSource feeds its live bed
availability). Every registered facility joins the candidate pool the allocation engine
searches. Live bed availability is held separately in ``bed_count`` (one row per bed type).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Numeric, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import pg_enum
from app.parameters import BedType, DataSource, Tier

if TYPE_CHECKING:
    from app.db.models.bed_count import BedCount


class Facility(Base):
    """A hospital/clinic in the referral network (docs/02-data-model.md §2.1)."""

    __tablename__ = "facility"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Unique so the seed script can upsert by name idempotently (docs/11 §5).
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # Decimal lat/long — no PostGIS; spatial work is done by the maps service (docs/02 header).
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    tier: Mapped[Tier] = mapped_column(pg_enum(Tier, "tier"), nullable=False)
    # Subset of bed types this facility offers (Postgres array of the bedtype enum).
    supported_bed_types: Mapped[list[BedType]] = mapped_column(
        ARRAY(pg_enum(BedType, "bedtype")), nullable=False
    )
    contact_phone: Mapped[str] = mapped_column(Text, nullable=False)
    active_data_source: Mapped[DataSource] = mapped_column(
        pg_enum(DataSource, "datasource"),
        nullable=False,
        default=DataSource.SIMULATION,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # selectin so the relationship loads as part of the query — async-safe, no lazy load
    # triggered on attribute access. Cascade deletes a facility's bed counts with it.
    bed_counts: Mapped[list[BedCount]] = relationship(
        back_populates="facility",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
