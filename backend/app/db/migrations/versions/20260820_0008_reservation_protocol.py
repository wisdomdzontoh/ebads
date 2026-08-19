"""reservation protocol: allocation, reservation, notification, decision_log (docs/02 §3.5-3.8)

Splits the former all-in-one ``emergency_request`` (request + outcome) into
``emergency_request`` (what was asked, unchanged shape minus the outcome columns) and
``allocation`` (the decision, with its own lifecycle status). Adds ``reservation`` (the held
bed's own lifetime, FR8/FR10), ``notification`` (FR19), and ``decision_log`` (FR12 replay).

Revision ID: 0008_reservation_protocol
Revises: 0007_spatial_retrieval
Create Date: 2026-08-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0008_reservation_protocol"
down_revision: str | None = "0007_spatial_retrieval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALLOCATION_STATUS = postgresql.ENUM(
    "pending", "confirmed", "arrived", "expired", "refused", "escalated",
    name="allocation_status",
)
NOTIFICATION_CHANNEL = postgresql.ENUM("sms", "push", name="notification_channel")
NOTIFICATION_DELIVERY_STATUS = postgresql.ENUM(
    "pending", "sent", "failed", name="notification_delivery_status"
)

# Columns that moved from emergency_request onto the new allocation table.
_MOVED_COLUMNS = (
    "algorithm_used",
    "weight_vector",
    "selection_reason",
    "recommended_facility_id",
    "travel_time_minutes",
    "is_estimated_travel_time",
    "capability_match",
    "candidates_evaluated",
    "status",
)


def upgrade() -> None:
    bind = op.get_bind()
    ALLOCATION_STATUS.create(bind, checkfirst=True)
    NOTIFICATION_CHANNEL.create(bind, checkfirst=True)
    NOTIFICATION_DELIVERY_STATUS.create(bind, checkfirst=True)

    op.create_table(
        "allocation",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("facility_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "strategy_used", postgresql.ENUM(name="algorithm", create_type=False), nullable=False
        ),
        sa.Column("weight_vector", postgresql.JSONB(), nullable=True),
        sa.Column("score", sa.Numeric(), nullable=True),
        sa.Column("travel_time_minutes", sa.Numeric(), nullable=True),
        sa.Column(
            "is_estimated_travel_time", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("eta_minutes", sa.Numeric(), nullable=True),
        sa.Column("capability_match", sa.Numeric(), nullable=True),
        sa.Column("candidates_evaluated", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("selection_reason", sa.Text(), nullable=False),
        sa.Column(
            "status", postgresql.ENUM(name="allocation_status", create_type=False), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["request_id"], ["emergency_request.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["facility_id"], ["facility.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_allocation_status", "allocation", ["status"])
    op.create_index("ix_allocation_created_at", "allocation", ["created_at"])

    op.create_table(
        "reservation",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("allocation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("facility_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bed_type", postgresql.ENUM(name="bedtype", create_type=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["allocation_id"], ["allocation.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["facility_id"], ["facility.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("allocation_id", name="uq_reservation_allocation_id"),
    )
    # docs/02 §4: partial index for the sweeper, which only ever looks at unreleased rows.
    op.execute(
        "CREATE INDEX idx_reservation_expires_at ON reservation (expires_at) "
        "WHERE released_at IS NULL"
    )

    op.create_table(
        "notification",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("allocation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "channel",
            postgresql.ENUM(name="notification_channel", create_type=False),
            nullable=False,
        ),
        sa.Column("recipient", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "delivery_status",
            postgresql.ENUM(name="notification_delivery_status", create_type=False),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["allocation_id"], ["allocation.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "decision_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("allocation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidates", postgresql.JSONB(), nullable=False),
        sa.Column("weights", postgresql.JSONB(), nullable=True),
        sa.Column("parameters_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("rejected_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["allocation_id"], ["allocation.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("allocation_id", name="uq_decision_log_allocation_id"),
    )

    # emergency_request keeps only its own facts; the outcome columns move to allocation.
    # DROP COLUMN cascades to any index/FK constraint defined on just that column.
    for column in _MOVED_COLUMNS:
        op.drop_column("emergency_request", column)


def downgrade() -> None:
    op.add_column(
        "emergency_request", sa.Column("candidates_evaluated", sa.Integer(), nullable=True)
    )
    op.add_column(
        "emergency_request", sa.Column("capability_match", sa.Numeric(), nullable=True)
    )
    op.add_column(
        "emergency_request",
        sa.Column(
            "is_estimated_travel_time", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )
    op.add_column(
        "emergency_request", sa.Column("travel_time_minutes", sa.Numeric(), nullable=True)
    )
    op.add_column(
        "emergency_request",
        sa.Column("recommended_facility_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "emergency_request_recommended_facility_id_fkey",
        "emergency_request",
        "facility",
        ["recommended_facility_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("emergency_request", sa.Column("selection_reason", sa.Text(), nullable=True))
    op.add_column(
        "emergency_request", sa.Column("weight_vector", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "emergency_request",
        sa.Column(
            "algorithm_used", postgresql.ENUM(name="algorithm", create_type=False), nullable=True
        ),
    )
    op.add_column(
        "emergency_request",
        sa.Column("status", postgresql.ENUM(name="status", create_type=False), nullable=True),
    )
    op.create_index("ix_emergency_request_status", "emergency_request", ["status"])

    op.drop_table("decision_log")
    op.drop_table("notification")
    op.execute("DROP INDEX IF EXISTS idx_reservation_expires_at")
    op.drop_table("reservation")
    op.drop_index("ix_allocation_created_at", table_name="allocation")
    op.drop_index("ix_allocation_status", table_name="allocation")
    op.drop_table("allocation")

    NOTIFICATION_DELIVERY_STATUS.drop(op.get_bind(), checkfirst=True)
    NOTIFICATION_CHANNEL.drop(op.get_bind(), checkfirst=True)
    ALLOCATION_STATUS.drop(op.get_bind(), checkfirst=True)
