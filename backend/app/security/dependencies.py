"""The RBAC single enforcement point (docs/01-architecture.md §4, docs/AGENTS.md §3).

``get_current_user`` resolves the bearer token to a live, active ``UserAccount``.
``require_permission(resource, action, facility_id_param=...)`` is a dependency *factory*:
every protected route attaches its result, and it is the only place in the codebase that
answers "is this call allowed" — no route handler contains its own role check.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.permission import Permission
from app.db.models.user_account import UserAccount
from app.db.session import get_session
from app.parameters import PermissionAction, PermissionScope, UserStatus
from app.security.jwt import InvalidTokenError, TokenType, decode_token

# auto_error=False: a missing header falls through to our own 401 below, mirroring the
# retired X-API-Key dependency's message quality (docs/01 §4).
_bearer = HTTPBearer(auto_error=False, description="Access token issued by POST /auth/login")


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserAccount:
    """Resolve the bearer token to a live, active ``UserAccount``, or raise 401.

    Looks the account up fresh on every call (rather than trusting the token's claims
    verbatim) so a suspension or role/facility change takes effect immediately, not only
    after the access token expires.
    """
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        claims = decode_token(credentials.credentials, TokenType.ACCESS)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid access token: {exc}") from exc

    user = await session.get(UserAccount, claims.user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "account is unknown or suspended")
    return user


CurrentUser = Annotated[UserAccount, Depends(get_current_user)]


def require_permission(
    resource: str,
    action: PermissionAction,
    facility_id_param: str | None = None,
    trust_service_scoping: bool = False,
) -> Callable[..., Coroutine[Any, Any, UserAccount]]:
    """Build a dependency that 403s unless the caller's role grants ``(resource, action)``.

    If the matched grant's scope is ``own_facility``, the caller is admitted only if:

    - ``facility_id_param`` names a path parameter, and it equals the caller's
      ``facility_id`` (FR17 — e.g. ``PUT /facilities/{facility_id}``); or
    - ``trust_service_scoping=True`` is passed explicitly, meaning the target facility is
      not in the path (e.g. it is read from the request body) and the *service* pins the
      write to ``current_user.facility_id`` regardless of what the body says — verified at
      the call site, not assumed here.

    Neither condition met -> 403, fail closed. This is deliberate: an own_facility grant
    with nothing to scope it against (no path param, no service pin) must never silently
    admit the caller, e.g. a facility_administrator's own_facility grant on ``facility``
    must not let them ``POST /facilities`` to create an unrelated new facility — there is
    no "own" facility yet for a create, and the service performs no pinning there.

    Returns the authorized ``UserAccount`` so routes can use its id/role/facility_id
    without a second lookup.
    """

    async def _dependency(
        request: Request,
        current_user: Annotated[UserAccount, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> UserAccount:
        grant = await session.scalar(
            select(Permission).where(
                Permission.role_id == current_user.role_id,
                Permission.resource == resource,
                Permission.action == action,
            )
        )
        if grant is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"role does not permit {action.value} on {resource}"
            )
        if grant.scope == PermissionScope.ALL:
            return current_user

        # own_facility: the caller must have a facility, and the target must be resolvable
        # and match it — either from the path, or via an explicitly-trusted service pin.
        if current_user.facility_id is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "no facility associated with account")
        if facility_id_param is not None:
            raw_target = request.path_params.get(facility_id_param)
            if raw_target is None:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "cross-facility access denied")
            target_facility_id = (
                raw_target if isinstance(raw_target, uuid.UUID) else uuid.UUID(str(raw_target))
            )
            if target_facility_id != current_user.facility_id:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "cross-facility access denied")
            return current_user
        if trust_service_scoping:
            return current_user
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cross-facility access denied")

    return _dependency
