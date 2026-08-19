"""Access/refresh JWT issuance and verification (docs/01 §4, docs/09-parameters.md §10).

Two token types share one signing key, distinguished by a ``type`` claim so a refresh
token can never be used to authenticate an API call and vice versa.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import jwt

from app.config import get_settings
from app.parameters import ACCESS_TOKEN_TTL_MIN, REFRESH_TOKEN_TTL_DAYS, Role

# [IMPL] not thesis-specified; standard HMAC choice for a single-key deployment.
_ALGORITHM = "HS256"


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class InvalidTokenError(Exception):
    """Raised for any decode failure: bad signature, expired, wrong type, malformed."""


@dataclass(frozen=True)
class TokenClaims:
    """Decoded, verified claims from an access or refresh token."""

    user_id: uuid.UUID
    role: Role
    facility_id: uuid.UUID | None
    token_type: TokenType


def _secret_key() -> str:
    key = get_settings().jwt_secret_key
    if not key:
        # Fails closed: unlike the retired static X-API-Key scheme, a missing secret must
        # never be treated as "auth disabled".
        raise RuntimeError("JWT_SECRET_KEY is not configured")
    return key


def _encode(
    user_id: uuid.UUID,
    role: Role,
    facility_id: uuid.UUID | None,
    token_type: TokenType,
    ttl: timedelta,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "facility_id": str(facility_id) if facility_id is not None else None,
        "type": token_type.value,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, _secret_key(), algorithm=_ALGORITHM)


def create_access_token(user_id: uuid.UUID, role: Role, facility_id: uuid.UUID | None) -> str:
    """Issue a short-lived access token (``ACCESS_TOKEN_TTL_MIN``)."""
    return _encode(
        user_id, role, facility_id, TokenType.ACCESS, timedelta(minutes=ACCESS_TOKEN_TTL_MIN)
    )


def create_refresh_token(user_id: uuid.UUID, role: Role, facility_id: uuid.UUID | None) -> str:
    """Issue a long-lived refresh token (``REFRESH_TOKEN_TTL_DAYS``)."""
    return _encode(
        user_id, role, facility_id, TokenType.REFRESH, timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    )


def decode_token(token: str, expect_type: TokenType) -> TokenClaims:
    """Verify signature + expiry and return typed claims, or raise ``InvalidTokenError``.

    ``expect_type`` rejects a refresh token presented as an access token and vice versa —
    the two are not interchangeable.
    """
    try:
        payload = jwt.decode(token, _secret_key(), algorithms=[_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    token_type = payload.get("type")
    if token_type != expect_type.value:
        raise InvalidTokenError(f"expected a {expect_type.value} token, got {token_type!r}")

    try:
        facility_id = payload["facility_id"]
        return TokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            role=Role(payload["role"]),
            facility_id=uuid.UUID(facility_id) if facility_id is not None else None,
            token_type=TokenType(token_type),
        )
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError(f"malformed token claims: {exc}") from exc
