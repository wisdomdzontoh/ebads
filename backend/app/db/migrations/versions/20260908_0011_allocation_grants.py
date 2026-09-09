"""facility_administrator allocation grants + system_administrator allocation:read (docs/02
§2.2, role/permission audit)

Two gaps found by auditing the seeded matrix (0005_auth_rbac) against the intended role
model (PRD use-case actors):

1. ``facility_administrator`` is supposed to be a strict superset of ``facility_staff``
   (every Facility Staff capability, plus account management) — the permission table is
   flat, not inherited (deliberately: see 0005's own seed style), so every
   ``facility_staff`` grant must be duplicated onto ``facility_administrator`` explicitly.
   ``facility_staff`` already holds ``allocation:write:own_facility`` (0005) and
   ``allocation:read:own_facility`` (0010); ``facility_administrator`` held neither, so a
   facility administrator could not view or act on their own facility's inbound
   reservations at all — the superset relationship did not hold.

2. ``system_administrator`` had no ``allocation`` grant of any kind — 403 on every
   allocation read endpoint. Read-only, and deliberately so: no matching ``write`` grant is
   added here. The absence of that row (not a mutation-blocking check anywhere else) IS the
   enforcement that system administrator oversight can never acknowledge, revoke, refuse, or
   confirm arrival on an allocation — see backend/tests/integration/test_rbac_matrix.py's
   coverage proving exactly that.

Investigated whether the matching ``bed_state:read`` grant is also missing for both
facility roles (raised by the same audit) — it is not a gap. ``GET /facilities`` and
``GET /facilities/{id}`` (gated by ``facility:read``, which every role already holds) embed
live ``bed_counts`` directly on the facility record (``FacilityRead.bed_counts``,
app/api/schemas/facility.py) — there is no separate "read bed state" action anywhere in the
codebase, only ``bed_state:write`` (the beds-update endpoint). Bed viewing is gated by the
``facility`` resource, not ``bed_state``; no grant added for it.

Same insert idiom as 0005/0010 (``INSERT ... SELECT id ... FROM role WHERE name = ...``).

Revision ID: 0011_allocation_grants
Revises: 0010_facility_allocation_read
Create Date: 2026-09-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_allocation_grants"
down_revision: str | None = "0010_facility_allocation_read"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (role, resource, action, scope) — exactly the three grants the audit specified.
_GRANTS: list[tuple[str, str, str, str]] = [
    ("system_administrator", "allocation", "read", "all"),
    ("facility_administrator", "allocation", "read", "own_facility"),
    ("facility_administrator", "allocation", "write", "own_facility"),
]


def upgrade() -> None:
    for role_name, resource, action, scope in _GRANTS:
        op.execute(
            sa.text(
                "INSERT INTO permission (role_id, resource, action, scope) "
                "SELECT id, :resource, :action ::permission_action, :scope ::permission_scope "
                "FROM role WHERE name = :role_name ::role_name"
            ).bindparams(role_name=role_name, resource=resource, action=action, scope=scope)
        )


def downgrade() -> None:
    for role_name, resource, action, scope in _GRANTS:
        op.execute(
            sa.text(
                "DELETE FROM permission WHERE resource = :resource AND action = :action "
                "::permission_action AND scope = :scope ::permission_scope "
                "AND role_id = (SELECT id FROM role WHERE name = :role_name ::role_name)"
            ).bindparams(role_name=role_name, resource=resource, action=action, scope=scope)
        )
