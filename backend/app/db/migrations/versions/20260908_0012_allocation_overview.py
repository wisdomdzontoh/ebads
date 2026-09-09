"""system_administrator allocation_overview:read:all — the cross-facility oversight grant
(docs/02 §2.2, role/permission audit, Task 2)

``GET /allocations/overview`` (the new oversight endpoint) needs a permission check that
admits ``system_administrator`` but NOT ``dispatcher`` — and ``dispatcher`` already holds
``allocation:read:all`` (0005_auth_rbac, for ``GET /allocations`` and
``GET /allocations/{id}``, further narrowed to the dispatcher's own requests by those
routes' own query filters, not by scope). Gating the new endpoint on
``allocation:read`` + scope ``all`` alone would therefore admit both roles identically —
the permission model has no notion of "this specific read grant, not that one" within a
single resource name, and scope only ever means own_facility-vs-unrestricted, not
who-vs-who.

Rather than add a role check in the route (the one thing AGENTS.md §3 and every existing
route in this file deliberately avoid — require_permission is the sole enforcement point)
or invent a new PermissionScope value (which would still leave dispatcher and
system_administrator both matching "unrestricted" and unable to be told apart), this adds a
DISTINCT resource name for the oversight capability: ``allocation_overview``. This is the
same mechanism the seed table already uses to separate capabilities that touch overlapping
data under different rules — ``facility`` vs ``bed_state`` vs ``user_account`` are all
their own resource strings despite all being "about a facility" — so a dispatcher's
``allocation:read:all`` grant has no bearing on a resource named ``allocation_overview``
at all, with zero special-casing anywhere. ``system_administrator`` is the only role
granted it, and only for ``read`` — no ``write`` action on this resource exists anywhere
in the codebase, which is what makes the endpoint structurally incapable of exposing a
mutation, not a check that could be bypassed or forgotten on a future route.

Revision ID: 0012_allocation_overview
Revises: 0011_allocation_grants
Create Date: 2026-09-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_allocation_overview"
down_revision: str | None = "0011_allocation_grants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLE = "system_administrator"
_RESOURCE = "allocation_overview"
_ACTION = "read"
_SCOPE = "all"


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO permission (role_id, resource, action, scope) "
            "SELECT id, :resource, :action ::permission_action, :scope ::permission_scope "
            "FROM role WHERE name = :role_name ::role_name"
        ).bindparams(role_name=_ROLE, resource=_RESOURCE, action=_ACTION, scope=_SCOPE)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM permission WHERE resource = :resource AND action = :action "
            "::permission_action AND scope = :scope ::permission_scope "
            "AND role_id = (SELECT id FROM role WHERE name = :role_name ::role_name)"
        ).bindparams(role_name=_ROLE, resource=_RESOURCE, action=_ACTION, scope=_SCOPE)
    )
