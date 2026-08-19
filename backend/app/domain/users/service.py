"""Account provisioning (docs/01 §4, EBADS_PRD.md §2): no self-service, every account has a creator.

Called only after the route's ``require_permission("user_account", ...)`` dependency has
already admitted the caller — the branching below is which *shape* of account that caller
may create, not whether they may create one at all.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.role import Role as RoleRow
from app.db.models.user_account import UserAccount
from app.domain.audit import service as audit
from app.parameters import Role
from app.security.passwords import hash_password


class UserProvisioningError(Exception):
    """Raised when the requested account shape is not one the caller may create."""


@dataclass(frozen=True)
class CreateUserInput:
    email: str
    password: str
    role: Role
    # Only meaningful when the actor is system_administrator; a facility_administrator's
    # new accounts are always pinned to the actor's own facility (docs/02 §2.3).
    facility_id: uuid.UUID | None = None


def _validate_facility_scope(role: Role, facility_id: uuid.UUID | None) -> None:
    """Mirror the docs/02 §2.3 invariant client-side, for a clean error before the DB trigger."""
    scoped = role in (Role.FACILITY_ADMINISTRATOR, Role.FACILITY_STAFF)
    if scoped and facility_id is None:
        raise UserProvisioningError(f"facility_id is required for role {role.value}")
    if not scoped and facility_id is not None:
        raise UserProvisioningError(f"facility_id must not be set for role {role.value}")


class UsersService:
    """Creates and lists ``user_account`` rows, scoped by the acting caller's role."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_user(self, actor: UserAccount, data: CreateUserInput) -> UserAccount:
        """Create an account on the acting user's behalf.

        ``system_administrator`` may create any role, at any facility (or none, for
        unscoped roles). ``facility_administrator`` may only create ``facility_staff`` or
        ``facility_administrator`` accounts, and only for their own facility — the
        payload's ``facility_id`` is ignored in that case, not merely validated, so a
        facility admin can never provision into a facility they do not belong to.
        """
        actor_role = Role(actor.role.name)
        if actor_role == Role.SYSTEM_ADMINISTRATOR:
            facility_id = data.facility_id
        elif actor_role == Role.FACILITY_ADMINISTRATOR:
            if data.role not in (Role.FACILITY_ADMINISTRATOR, Role.FACILITY_STAFF):
                raise UserProvisioningError(
                    "facility administrators may only create facility_administrator or "
                    "facility_staff accounts"
                )
            facility_id = actor.facility_id
        else:
            raise UserProvisioningError(f"role {actor_role.value} cannot create accounts")

        _validate_facility_scope(data.role, facility_id)

        role_row = await self._session.scalar(select(RoleRow).where(RoleRow.name == data.role))
        if role_row is None:
            raise UserProvisioningError(f"role {data.role.value} is not seeded")

        user = UserAccount(
            email=data.email,
            password_hash=hash_password(data.password),
            role_id=role_row.id,
            facility_id=facility_id,
            created_by=actor.id,
        )
        self._session.add(user)
        await self._session.flush()  # assigns user.id for the audit row below
        await audit.record(
            self._session,
            actor.id,
            "create",
            "user_account",
            user.id,
            {"email": data.email, "role": data.role.value, "facility_id": str(facility_id)},
        )
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def list_users(self, actor: UserAccount) -> list[UserAccount]:
        """List accounts visible to the caller.

        All accounts for ``system_administrator``; only the caller's own facility for
        ``facility_administrator``. The route's ``require_permission`` already limits who
        reaches this method at all.
        """
        actor_role = Role(actor.role.name)
        query = select(UserAccount).order_by(UserAccount.email)
        if actor_role == Role.FACILITY_ADMINISTRATOR:
            query = query.where(UserAccount.facility_id == actor.facility_id)
        result = await self._session.scalars(query)
        return list(result.all())
