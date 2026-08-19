"""auth + RBAC: role, permission, user_account, facility_request, audit_log (docs/02 §2)

Hand-written, matching the style of 0001: enum types created explicitly, tables created
explicitly, so creation order is deterministic. Roles and permissions are seeded here
(docs/02 §6 — "behaviour, not sample data"), not by a script.

The user_account invariant "facility-scoped roles require facility_id, unscoped roles
forbid it" (docs/02 §2.3) spans two tables (it depends on role.name via role_id), which a
plain Postgres CHECK constraint cannot express. It is enforced here with an equivalent
BEFORE INSERT OR UPDATE trigger instead, and mirrored in domain/users/service.py for a
clean 422 instead of a raw DB error.

Revision ID: 0005_auth_rbac
Revises: 0004_simulation_allocation_event
Create Date: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005_auth_rbac"
down_revision: str | None = "0004_simulation_allocation_event"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE_NAME = postgresql.ENUM(
    "system_administrator",
    "facility_administrator",
    "facility_staff",
    "dispatcher",
    name="role_name",
)
PERMISSION_ACTION = postgresql.ENUM("read", "write", "approve", name="permission_action")
PERMISSION_SCOPE = postgresql.ENUM("own_facility", "all", name="permission_scope")
USER_STATUS = postgresql.ENUM("active", "suspended", name="user_status")
FACILITY_REQUEST_STATUS = postgresql.ENUM(
    "pending", "approved", "rejected", name="facility_request_status"
)

# (role, resource, action, scope) — the PRD §2 role table translated into data.
_PERMISSIONS: list[tuple[str, str, str, str]] = [
    ("system_administrator", "facility_request", "read", "all"),
    ("system_administrator", "facility_request", "approve", "all"),
    ("system_administrator", "user_account", "write", "all"),
    ("system_administrator", "user_account", "read", "all"),
    ("facility_administrator", "user_account", "read", "own_facility"),
    ("system_administrator", "config", "read", "all"),
    ("system_administrator", "config", "write", "all"),
    ("system_administrator", "audit_log", "read", "all"),
    # Internal/seed facility creation, bypassing the registration flow (docs/04 old §3).
    ("system_administrator", "facility", "write", "all"),
    # [IMPL] "simulation" is not a docs/02 §2.2 resource — the PRD role table does not
    # describe simulation access for any role. This is a minimal retrofit gating the
    # legacy discrete-event simulation API (being replaced wholesale by the scenario
    # runner in Increment 5) behind *a* role rather than leaving it open; revisit there.
    ("system_administrator", "simulation", "write", "all"),
    ("system_administrator", "simulation", "read", "all"),
    ("facility_administrator", "user_account", "write", "own_facility"),
    ("facility_administrator", "facility", "write", "own_facility"),
    ("facility_administrator", "bed_state", "write", "own_facility"),
    ("facility_staff", "bed_state", "write", "own_facility"),
    ("facility_staff", "allocation", "write", "own_facility"),
    ("dispatcher", "allocation", "write", "all"),
    ("dispatcher", "allocation", "read", "all"),
    # Every role can read the registry (needed to submit/route a request at all).
    ("system_administrator", "facility", "read", "all"),
    ("facility_administrator", "facility", "read", "all"),
    ("facility_staff", "facility", "read", "all"),
    ("dispatcher", "facility", "read", "all"),
]

_ROLE_DESCRIPTIONS: dict[str, str] = {
    "system_administrator": "Approves facility registrations, provisions dispatcher "
    "accounts, configures study parameters, reads the audit log.",
    "facility_administrator": "Manages accounts and bed availability for one facility; "
    "configures that facility's EMR adapter.",
    "facility_staff": "Updates bed availability and acknowledges incoming allocations "
    "for one facility.",
    "dispatcher": "Submits emergency requests and confirms patient arrival.",
}


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    ROLE_NAME.create(bind, checkfirst=True)
    PERMISSION_ACTION.create(bind, checkfirst=True)
    PERMISSION_SCOPE.create(bind, checkfirst=True)
    USER_STATUS.create(bind, checkfirst=True)
    FACILITY_REQUEST_STATUS.create(bind, checkfirst=True)

    op.create_table(
        "role",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", postgresql.ENUM(name="role_name", create_type=False), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_role_name"),
    )

    op.create_table(
        "permission",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column(
            "action", postgresql.ENUM(name="permission_action", create_type=False), nullable=False
        ),
        sa.Column(
            "scope", postgresql.ENUM(name="permission_scope", create_type=False), nullable=False
        ),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "role_id", "resource", "action", name="uq_permission_role_resource_action"
        ),
    )

    op.create_table(
        "user_account",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("facility_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="user_status", create_type=False),
            server_default="active",
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"]),
        sa.ForeignKeyConstraint(["facility_id"], ["facility.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["user_account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_user_account_email"),
    )
    op.create_index("ix_user_account_facility_id", "user_account", ["facility_id"])

    op.create_table(
        "facility_request",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("facility_name", sa.Text(), nullable=False),
        sa.Column("ghs_code", sa.Text(), nullable=False),
        sa.Column("tier", postgresql.ENUM(name="tier", create_type=False), nullable=False),
        sa.Column("contact_email", sa.Text(), nullable=False),
        sa.Column("contact_phone", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="facility_request_status", create_type=False),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["reviewed_by"], ["user_account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column(
            "detail",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "logged_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_logged_at", "audit_log", ["logged_at"])
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])

    op.add_column(
        "emergency_request",
        sa.Column("dispatcher_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_emergency_request_dispatcher_id",
        "emergency_request",
        "user_account",
        ["dispatcher_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # docs/02 §2.3 invariant, enforced as a trigger because it spans user_account + role
    # (see module docstring — a plain CHECK constraint cannot join across tables).
    op.execute(
        """
        CREATE FUNCTION enforce_user_account_facility_scope() RETURNS trigger AS $$
        DECLARE
            resolved_role_name text;
        BEGIN
            SELECT name INTO resolved_role_name FROM role WHERE id = NEW.role_id;
            IF resolved_role_name IN ('facility_administrator', 'facility_staff')
                AND NEW.facility_id IS NULL THEN
                RAISE EXCEPTION
                    'facility_id is required for role %', resolved_role_name;
            END IF;
            IF resolved_role_name IN ('system_administrator', 'dispatcher')
                AND NEW.facility_id IS NOT NULL THEN
                RAISE EXCEPTION
                    'facility_id must be null for role %', resolved_role_name;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_user_account_facility_scope
        BEFORE INSERT OR UPDATE ON user_account
        FOR EACH ROW EXECUTE FUNCTION enforce_user_account_facility_scope()
        """
    )

    # Seed roles. Explicit ::role_name casts: the driver binds a plain string parameter as
    # VARCHAR, which Postgres will not implicitly cast onto a custom enum column/comparison.
    # NOTE the space before every `::` — `sa.text()`'s bind-param parser mis-scans a cast
    # written directly against a parameter (`:name::role_name` parses as bind param "nam",
    # dropping the last character); a space avoids the ambiguity and is valid SQL either way.
    for name, description in _ROLE_DESCRIPTIONS.items():
        op.execute(
            sa.text(
                "INSERT INTO role (name, description) VALUES (:name ::role_name, :description)"
            ).bindparams(name=name, description=description)
        )

    # Seed permissions, resolving role_id by name so no UUID needs to be hardcoded.
    for role_name, resource, action, scope in _PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permission (role_id, resource, action, scope) "
                "SELECT id, :resource, :action ::permission_action, :scope ::permission_scope "
                "FROM role WHERE name = :role_name ::role_name"
            ).bindparams(role_name=role_name, resource=resource, action=action, scope=scope)
        )


def downgrade() -> None:
    op.drop_constraint(
        "fk_emergency_request_dispatcher_id", "emergency_request", type_="foreignkey"
    )
    op.drop_column("emergency_request", "dispatcher_id")

    op.execute("DROP TRIGGER IF EXISTS trg_user_account_facility_scope ON user_account")
    op.execute("DROP FUNCTION IF EXISTS enforce_user_account_facility_scope()")

    op.drop_table("audit_log")
    op.drop_table("facility_request")
    op.drop_table("user_account")
    op.drop_table("permission")
    op.drop_table("role")

    FACILITY_REQUEST_STATUS.drop(op.get_bind(), checkfirst=True)
    USER_STATUS.drop(op.get_bind(), checkfirst=True)
    PERMISSION_SCOPE.drop(op.get_bind(), checkfirst=True)
    PERMISSION_ACTION.drop(op.get_bind(), checkfirst=True)
    ROLE_NAME.drop(op.get_bind(), checkfirst=True)
