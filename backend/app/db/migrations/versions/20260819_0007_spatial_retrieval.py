"""spatial retrieval: facility.location geography + GIST index (docs/01 §2, docs/02 §3.1, FR3)

Enables PostGIS and adds ``facility.location`` as a ``geography(Point,4326)`` column
**generated** from the existing ``latitude``/``longitude`` columns — so the two
representations can never drift, and no application code needs to keep them in sync.
``latitude``/``longitude`` stay as plain columns (the API contract the mobile app and portal
already depend on keeps working unchanged); ``location`` is the query-optimised derived
form the GIST index and ``ST_DWithin`` retrieval query use (``domain/allocation/service.py``).

Revision ID: 0007_spatial_retrieval
Revises: 0006_bed_state_versioning
Create Date: 2026-08-19
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_spatial_retrieval"
down_revision: str | None = "0006_bed_state_versioning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute(
        """
        ALTER TABLE facility
        ADD COLUMN location geography(Point, 4326)
        GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography) STORED
        """
    )
    # docs/02 §4: "facility USING GIST (location) — required by FR3; absence is a defect."
    op.execute("CREATE INDEX idx_facility_location ON facility USING GIST (location)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_facility_location")
    op.execute("ALTER TABLE facility DROP COLUMN location")
    # Extension left in place on downgrade — dropping it is a cluster-wide action or could
    # affect other objects; CREATE EXTENSION IF NOT EXISTS on a future upgrade is a no-op
    # either way.
