"""bed_state versioning + adapter roster rename (docs/01 §5, docs/02 §3.1-3.2)

Adds the compare-and-set ``version`` column (+ ``updated_by``) to ``bed_count``, required by
``ManualAdapter.reserve`` (``domain/beds/manual_adapter.py``). Also recreates the
``datasource`` enum with the current adapter roster (``manual``/``ghs_data``/``fhir_r4``/
``rest_polling``, replacing the previous simulation-era labels) and makes
``facility.active_data_source`` nullable — null now means manual maintenance (docs/02 §3.1).
The column is not consumed anywhere yet (no code reads it — confirmed by grep before writing
this migration), so recreating the type is a value-set correction, not a data-migration.

Revision ID: 0006_bed_state_versioning
Revises: 0005_auth_rbac
Create Date: 2026-08-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006_bed_state_versioning"
down_revision: str | None = "0005_auth_rbac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_DATASOURCE_LABELS = ("simulation", "facility_management", "national_emr", "hl7_fhir")
_NEW_DATASOURCE_LABELS = ("manual", "ghs_data", "fhir_r4", "rest_polling")


def upgrade() -> None:
    op.add_column(
        "bed_count",
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "bed_count",
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_bed_count_updated_by",
        "bed_count",
        "user_account",
        ["updated_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # Postgres cannot alter enum labels in place (rename covers one-for-one renames, not a
    # different value set) and cannot drop a type still referenced by a column — drop the
    # column, drop the type, recreate both.
    op.drop_column("facility", "active_data_source")
    op.execute("DROP TYPE datasource")
    new_datasource = postgresql.ENUM(*_NEW_DATASOURCE_LABELS, name="datasource")
    new_datasource.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "facility",
        sa.Column(
            "active_data_source",
            postgresql.ENUM(name="datasource", create_type=False),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("facility", "active_data_source")
    op.execute("DROP TYPE datasource")
    old_datasource = postgresql.ENUM(*_OLD_DATASOURCE_LABELS, name="datasource")
    old_datasource.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "facility",
        sa.Column(
            "active_data_source",
            postgresql.ENUM(name="datasource", create_type=False),
            server_default="simulation",
            nullable=False,
        ),
    )

    op.drop_constraint("fk_bed_count_updated_by", "bed_count", type_="foreignkey")
    op.drop_column("bed_count", "updated_by")
    op.drop_column("bed_count", "version")
