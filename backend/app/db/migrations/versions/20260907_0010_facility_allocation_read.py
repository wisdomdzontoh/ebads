"""facility_staff allocation:read grant, own_facility scope (docs/02 §2.2, Task 3)

``facility_staff`` already had ``allocation:write:own_facility`` (0005_auth_rbac —
acknowledge/refuse/revoke) but no ``read`` grant at all, so the inbound-reservations view
(``GET /allocations/inbound``, web portal Task 3) had nothing to gate on. Adds the missing
read grant at the same scope, rather than widening write. Same insert idiom as 0005's own
permission seed (`INSERT ... SELECT id ... FROM role WHERE name = ...`).

Revision ID: 0010_facility_allocation_read
Revises: 0009_reservation_revocation
Create Date: 2026-09-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_facility_allocation_read"
down_revision: str | None = "0009_reservation_revocation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLE = "facility_staff"
_RESOURCE = "allocation"
_ACTION = "read"
_SCOPE = "own_facility"


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
