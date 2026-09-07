"""reservation revocation + re-allocation: supersession, REVOKED status (docs/02 §3.5-3.6, FR24-27)

Adds ``allocation.supersedes_allocation_id`` (the re-allocation traces back to what it
replaced), ``reservation.revoked_at``/``revocation_reason``, and a ``revoked`` value on the
``allocation_status`` enum — distinct from ``refused`` (docs/01 §7): a reservation is a
coordination claim the facility can withdraw before arrival, not a clinical entitlement.

Revision ID: 0009_reservation_revocation
Revises: 0008_reservation_protocol
Create Date: 2026-09-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0009_reservation_revocation"
down_revision: str | None = "0008_reservation_protocol"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ORIGINAL_VALUES = ("pending", "confirmed", "arrived", "expired", "refused", "escalated")


def upgrade() -> None:
    # Postgres 12+ allows ADD VALUE inside a transaction; the one restriction that remains
    # (the new value cannot be referenced in the same transaction it was added in) does not
    # apply here — nothing below uses 'revoked' as a literal.
    op.execute("ALTER TYPE allocation_status ADD VALUE 'revoked'")

    op.add_column(
        "allocation",
        sa.Column("supersedes_allocation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "allocation_supersedes_allocation_id_fkey",
        "allocation",
        "allocation",
        ["supersedes_allocation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_allocation_supersedes_allocation_id", "allocation", ["supersedes_allocation_id"]
    )

    op.add_column("reservation", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reservation", sa.Column("revocation_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("reservation", "revocation_reason")
    op.drop_column("reservation", "revoked_at")

    op.drop_index("ix_allocation_supersedes_allocation_id", table_name="allocation")
    op.drop_constraint(
        "allocation_supersedes_allocation_id_fkey", "allocation", type_="foreignkey"
    )
    op.drop_column("allocation", "supersedes_allocation_id")

    # Postgres has no ALTER TYPE ... DROP VALUE. Recreate the enum without 'revoked' — this
    # fails (correctly) if any allocation row is currently 'revoked': there is no value to
    # downgrade it to, the same way any column-narrowing migration fails on data it can't fit.
    op.execute("ALTER TYPE allocation_status RENAME TO allocation_status_old")
    restored = postgresql.ENUM(*_ORIGINAL_VALUES, name="allocation_status")
    restored.create(op.get_bind())
    op.execute(
        "ALTER TABLE allocation ALTER COLUMN status TYPE allocation_status "
        "USING status::text::allocation_status"
    )
    op.execute("DROP TYPE allocation_status_old")
