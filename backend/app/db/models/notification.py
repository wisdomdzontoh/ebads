"""``notification`` — the SMS sent to the receiving facility (docs/02-data-model.md §3.7, FR19).

One row per delivery attempt's outcome. ``payload`` carries exactly the four documented
fields (urgency, bed_type, eta, reference — FR19's accept criterion), so the record alone
proves what was actually sent without needing to reconstruct it from other tables.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import pg_enum
from app.parameters import NotificationChannel, NotificationDeliveryStatus


class Notification(Base):
    """One notification attempt for an allocation (docs/02-data-model.md §3.7)."""

    __tablename__ = "notification"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    allocation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("allocation.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        pg_enum(NotificationChannel, "notification_channel"), nullable=False
    )
    recipient: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_status: Mapped[NotificationDeliveryStatus] = mapped_column(
        pg_enum(NotificationDeliveryStatus, "notification_delivery_status"), nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
