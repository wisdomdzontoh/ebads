"""Account provisioning (docs/02 §2.3). ``require_permission`` admits both

system_administrator and facility_administrator for ``write``/``read`` on ``user_account``;
``domain/users/service.py`` narrows what shape of account each may actually create.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.user import UserCreate, UserRead
from app.db.models.user_account import UserAccount
from app.db.session import get_session
from app.domain.users.service import CreateUserInput, UserProvisioningError, UsersService
from app.parameters import PermissionAction
from app.security.dependencies import require_permission

router = APIRouter(prefix="/users", tags=["users"])


def _service(session: Annotated[AsyncSession, Depends(get_session)]) -> UsersService:
    return UsersService(session)


ServiceDep = Annotated[UsersService, Depends(_service)]
# trust_service_scoping=True: UsersService pins a facility_administrator's writes/reads to
# their own facility_id regardless of what the request asks for (domain/users/service.py),
# so the own_facility grant is safe to admit even though "facility_id" is not a path param
# here — the target facility comes from the (ignored/overridden) body, not the path.
WriterDep = Annotated[
    UserAccount,
    Depends(require_permission("user_account", PermissionAction.WRITE, trust_service_scoping=True)),
]
ReaderDep = Annotated[
    UserAccount,
    Depends(require_permission("user_account", PermissionAction.READ, trust_service_scoping=True)),
]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserRead)
async def create_user(payload: UserCreate, service: ServiceDep, actor: WriterDep) -> UserRead:
    """Create a dispatcher, facility_staff, or facility_administrator account (FR16)."""
    try:
        user = await service.create_user(
            actor,
            CreateUserInput(
                email=payload.email,
                password=payload.password,
                role=payload.role,
                facility_id=payload.facility_id,
            ),
        )
    except UserProvisioningError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return UserRead.model_validate(user)


@router.get("", response_model=list[UserRead])
async def list_users(service: ServiceDep, actor: ReaderDep) -> list[UserRead]:
    """List accounts visible to the caller.

    All accounts for system_administrator; only the caller's own facility for
    facility_administrator.
    """
    users = await service.list_users(actor)
    return [UserRead.model_validate(u) for u in users]
