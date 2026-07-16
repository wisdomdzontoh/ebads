"""simulation allocation event (docs/02-data-model.md §2.6)

Adds the per-event record table the simulation engine writes on each processed event. No new
enum types are introduced: ``urgency`` / ``bedtype`` / ``status`` already exist (0001, 0003),
so all enum columns reference them with ``create_type=False``. The
``(session_id, event_index)`` index backs ordered per-session reads (docs/02 §3).

Revision ID: 0004_simulation_allocation_event
Revises: 0003_emergency_request
Create Date: 2026-07-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004_simulation_allocation_event"
down_revision: str | None = "0003_emergency_request"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "simulation_allocation_event",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_index", sa.Integer(), nullable=False),
        sa.Column("virtual_arrival_min", sa.Numeric(), nullable=False),
        sa.Column("urgency", postgresql.ENUM(name="urgency", create_type=False), nullable=False),
        sa.Column(
            "required_bed_type",
            postgresql.ENUM(name="bedtype", create_type=False),
            nullable=False,
        ),
        sa.Column("patient_lat", sa.Numeric(9, 6), nullable=False),
        sa.Column("patient_lon", sa.Numeric(9, 6), nullable=False),
        sa.Column("recommended_facility_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("travel_time_minutes", sa.Numeric(), nullable=True),
        sa.Column("time_to_bed_placement_min", sa.Numeric(), nullable=True),
        sa.Column("capability_match", sa.Numeric(), nullable=True),
        sa.Column("candidates_evaluated", sa.Integer(), nullable=False),
        sa.Column("status", postgresql.ENUM(name="status", create_type=False), nullable=False),
        sa.Column("los_minutes", sa.Numeric(), nullable=True),
        sa.Column("bed_release_virtual_min", sa.Numeric(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["simulation_session.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["recommended_facility_id"], ["facility.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sim_alloc_event_session_event_index",
        "simulation_allocation_event",
        ["session_id", "event_index"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sim_alloc_event_session_event_index",
        table_name="simulation_allocation_event",
    )
    op.drop_table("simulation_allocation_event")
