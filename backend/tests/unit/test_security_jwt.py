"""Access/refresh JWT tests (docs/01 §4, docs/09-parameters.md §10)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest

from app.config import Settings
from app.parameters import Role
from app.security import jwt as jwt_module
from app.security.jwt import (
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
)

_USER_ID = uuid.uuid4()
_FACILITY_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def _configured_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(
        jwt_module, "get_settings", lambda: Settings(jwt_secret_key="unit-test-key")
    )
    yield


def test_access_token_round_trips() -> None:
    token = create_access_token(_USER_ID, Role.DISPATCHER, None)
    claims = decode_token(token, TokenType.ACCESS)
    assert claims.user_id == _USER_ID
    assert claims.role == Role.DISPATCHER
    assert claims.facility_id is None
    assert claims.token_type == TokenType.ACCESS


def test_refresh_token_carries_facility_id() -> None:
    token = create_refresh_token(_USER_ID, Role.FACILITY_ADMINISTRATOR, _FACILITY_ID)
    claims = decode_token(token, TokenType.REFRESH)
    assert claims.facility_id == _FACILITY_ID


def test_access_token_rejected_as_refresh_token() -> None:
    token = create_access_token(_USER_ID, Role.DISPATCHER, None)
    with pytest.raises(InvalidTokenError):
        decode_token(token, TokenType.REFRESH)


def test_refresh_token_rejected_as_access_token() -> None:
    token = create_refresh_token(_USER_ID, Role.DISPATCHER, None)
    with pytest.raises(InvalidTokenError):
        decode_token(token, TokenType.ACCESS)


def test_garbage_token_is_rejected() -> None:
    with pytest.raises(InvalidTokenError):
        decode_token("not-a-jwt-at-all", TokenType.ACCESS)


def test_expired_token_is_rejected() -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": str(_USER_ID),
        "role": Role.DISPATCHER.value,
        "facility_id": None,
        "type": TokenType.ACCESS.value,
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
    }
    expired = pyjwt.encode(payload, "unit-test-key", algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        decode_token(expired, TokenType.ACCESS)


def test_wrong_signing_key_is_rejected() -> None:
    token = create_access_token(_USER_ID, Role.DISPATCHER, None)
    forged = pyjwt.decode(token, options={"verify_signature": False})
    retokened = pyjwt.encode(forged, "a-different-key", algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        decode_token(retokened, TokenType.ACCESS)


def test_missing_secret_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jwt_module, "get_settings", lambda: Settings(jwt_secret_key=""))
    with pytest.raises(RuntimeError):
        create_access_token(_USER_ID, Role.DISPATCHER, None)
