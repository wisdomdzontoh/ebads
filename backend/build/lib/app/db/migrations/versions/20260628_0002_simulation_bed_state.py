"""simulation session + isolated bed state (docs/02-data-model.md §2.4-2.5)

Adds the ``algorithm`` enum and the ``simulation_session`` / ``simulation_bed_state``
tables. These back the Bridge's ``SimulationDataSource`` (docs/01 §3.2): a run reads and
decrements bed availability here, never touching ``facility`` / ``bed_count``.

Revision ID: 0002_simulation_bed_state
Revises: 0001_facility_registry
Create Date: 2026-06-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_simulation_bed_state"
down_revision: str | None = "0001_facility_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# New enum for which algorithm a session runs (docs/02 §2.4). bedtype already exists (0001).
ALGORITHM = postgresql.ENUM("greedy", "weighted", "urgency_adaptive", name="algorithm")


def upgrade() -> None:
    bind = op.get_bind()
    ALGORITHM.create(bind, checkfirst=True)

    op.create_table(
        "simulation_session",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "algorithm_config",
            postgresql.ENUM(name="algorithm", create_type=False),
            nullable=False,
        ),
        sa.Column("occupancy_scenario", sa.Numeric(3, 2), nullable=False),
        sa.Column("weight_config", postgresql.JSONB(), nullable=True),
        sa.Column("radius_config", postgresql.JSONB(), nullable=True),
        sa.Column("capability_config", postgresql.JSONB(), nullable=True),
        sa.Column("random_seed", sa.BigInteger(), nullable=False),
        sa.Column("events_planned", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "simulation_bed_state",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("facility_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bed_type", postgresql.ENUM(name="bedtype", create_type=False), nullable=False),
        sa.Column("available", sa.Integer(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["simulation_session.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["facility_id"], ["facility.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "facility_id",
            "bed_type",
            name="uq_sim_bed_state_session_facility_bedtype",
        ),
        sa.CheckConstraint("available >= 0", name="ck_sim_bed_state_available_nonneg"),
        sa.CheckConstraint("available <= capacity", name="ck_sim_bed_state_available_le_capacity"),
    )


def downgrade() -> None:
    op.drop_table("simulation_bed_state")
    op.drop_table("simulation_session")
    ALGORITHM.drop(op.get_bind(), checkfirst=True)
