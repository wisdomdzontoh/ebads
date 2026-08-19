"""Login and token refresh (EBADS_PRD.md §10). Both endpoints are unauthenticated by definition."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    PasswordChangeRequest,
    RefreshRequest,
    TokenResponse,
)
from app.db.session import get_session
from app.domain.auth.service import (
    AuthService,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    WrongPasswordError,
)
from app.security.dependencies import CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])


def _service(session: Annotated[AsyncSession, Depends(get_session)]) -> AuthService:
    return AuthService(session)


ServiceDep = Annotated[AuthService, Depends(_service)]


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, service: ServiceDep) -> TokenResponse:
    """Authenticate by email + password; return an access/refresh token pair (FR15)."""
    try:
        tokens = await service.login(payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "invalid email or password"
        ) from exc
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        role=tokens.role,
        facility_id=tokens.facility_id,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(payload: RefreshRequest, service: ServiceDep) -> AccessTokenResponse:
    """Exchange a valid refresh token for a new access token."""
    try:
        access_token = await service.refresh(payload.refresh_token)
    except InvalidRefreshTokenError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "invalid or expired refresh token"
        ) from exc
    return AccessTokenResponse(access_token=access_token)


@router.patch("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChangeRequest, service: ServiceDep, actor: CurrentUser
) -> None:
    """Self-service password change — every authenticated role, own account only."""
    try:
        await service.change_password(actor, payload.current_password, payload.new_password)
    except WrongPasswordError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "current password is incorrect") from exc
