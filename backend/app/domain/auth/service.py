"""Login and token refresh (docs/01-architecture.md §4, EBADS_PRD.md §10).

Owns exactly two things the rest of the codebase should not duplicate: verifying a
password against the stored hash, and minting the token pair. Role-based access decisions
live in ``app/security/dependencies.py``, not here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user_account import UserAccount
from app.domain.audit import service as audit
from app.parameters import Role, UserStatus
from app.security.jwt import InvalidTokenError as _InvalidTokenError
from app.security.jwt import TokenType, create_access_token, create_refresh_token, decode_token
from app.security.passwords import verify_password


class InvalidCredentialsError(Exception):
    """Raised for an unknown email, wrong password, or a non-active account."""


class InvalidRefreshTokenError(Exception):
    """Raised when a refresh token is invalid, expired, or its account is gone/suspended."""


@dataclass(frozen=True)
class TokenPair:
    """The full login response (EBADS_PRD.md §10)."""

    access_token: str
    refresh_token: str
    role: Role
    facility_id: uuid.UUID | None


class AuthService:
    """Password verification and token issuance over a request-scoped session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def login(self, email: str, password: str) -> TokenPair:
        """Verify credentials, update ``last_login_at``, audit-log the login, return tokens."""
        user = await self._session.scalar(
            select(UserAccount).where(UserAccount.email == email)
        )
        if user is None or user.status != UserStatus.ACTIVE:
            raise InvalidCredentialsError("unknown email or inactive account")
        if not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("wrong password")

        user.last_login_at = datetime.now(UTC)
        await audit.record(self._session, user.id, "login", "user_account", user.id)
        await self._session.commit()

        role = Role(user.role.name)
        return TokenPair(
            access_token=create_access_token(user.id, role, user.facility_id),
            refresh_token=create_refresh_token(user.id, role, user.facility_id),
            role=role,
            facility_id=user.facility_id,
        )

    async def refresh(self, refresh_token: str) -> str:
        """Verify a refresh token and mint a new access token (not a new refresh token)."""
        try:
            claims = decode_token(refresh_token, TokenType.REFRESH)
        except _InvalidTokenError as exc:
            raise InvalidRefreshTokenError(str(exc)) from exc

        user = await self._session.get(UserAccount, claims.user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise InvalidRefreshTokenError("account is unknown or suspended")
        return create_access_token(user.id, Role(user.role.name), user.facility_id)
