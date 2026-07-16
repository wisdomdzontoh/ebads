"""emergency_request audit table (docs/02-data-model.md §2.3)

Adds the ``urgency`` and ``status`` enums and the ``emergency_request`` audit table. The
``algorithm`` and ``bedtype`` enums already exist (migrations 0002 / 0001).

Revision ID: 0003_emergency_request
Revises: 0002_simulation_bed_state
Create Date: 2026-06-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_emergency_request"
down_revision: str | None = "0002_simulation_bed_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

URGENCY = postgresql.ENUM("critical", "urgent", "standard", name="urgency")
STATUS = postgresql.ENUM("pending", "allocated", "escalated", name="status")


def upgrade() -> None:
    bind = op.get_bind()
    URGENCY.create(bind, checkfirst=True)
    STATUS.create(bind, checkfirst=True)

    op.create_table(
        "emergency_request",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("patient_lat", sa.Numeric(9, 6), nullable=False),
        sa.Column("patient_lon", sa.Numeric(9, 6), nullable=False),
        sa.Column("urgency", postgresql.ENUM(name="urgency", create_type=False), nullable=True),
        sa.Column(
            "required_bed_type",
            postgresql.ENUM(name="bedtype", create_type=False),
            nullable=False,
        ),
        sa.Column("simulation_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "algorithm_used",
            postgresql.ENUM(name="algorithm", create_type=False),
            nullable=False,
        ),
        sa.Column("weight_vector", postgresql.JSONB(), nullable=True),
        sa.Column("selection_reason", sa.Text(), nullable=False),
        sa.Column("recommended_facility_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("travel_time_minutes", sa.Numeric(), nullable=True),
        sa.Column(
            "is_estimated_travel_time",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("capability_match", sa.Numeric(), nullable=True),
        sa.Column("candidates_evaluated", sa.Integer(), nullable=False),
        sa.Column("status", postgresql.ENUM(name="status", create_type=False), nullable=False),
        sa.ForeignKeyConstraint(
            ["simulation_session_id"], ["simulation_session.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["recommended_facility_id"], ["facility.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_emergency_request_created_at", "emergency_request", ["created_at"])
    op.create_index("ix_emergency_request_status", "emergency_request", ["status"])


def downgrade() -> None:
    op.drop_index("ix_emergency_request_status", table_name="emergency_request")
    op.drop_index("ix_emergency_request_created_at", table_name="emergency_request")
    op.drop_table("emergency_request")
    STATUS.drop(op.get_bind(), checkfirst=True)
    URGENCY.drop(op.get_bind(), checkfirst=True)
