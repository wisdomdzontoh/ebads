"""X-API-Key enforcement tests (docs/04-api-spec.md §1, app/api/security.py).

The contract under test:
  - a configured key rejects requests with a missing or wrong ``X-API-Key`` (401) and
    admits the correct one, short-circuiting BEFORE any route/DB work;
  - a blank configured key disables the check entirely (test/dev mode);
  - health probes are never authenticated.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import security
from app.config import Settings
from app.main import create_app


@pytest.fixture()
def configured_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Point the security module at settings with a known static key."""
    key = "test-static-key"
    monkeypatch.setattr(security, "get_settings", lambda: Settings(api_key=key))
    yield key


def test_correct_key_is_admitted(configured_key: str) -> None:
    assert security.require_api_key(provided=configured_key) is None


@pytest.mark.parametrize("provided", [None, "", "wrong-key"])
def test_missing_or_wrong_key_is_rejected_with_401(
    configured_key: str, provided: str | None
) -> None:
    with pytest.raises(HTTPException) as excinfo:
        security.require_api_key(provided=provided)
    assert excinfo.value.status_code == 401


def test_blank_configured_key_disables_the_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "get_settings", lambda: Settings(api_key=""))
    assert security.require_api_key(provided=None) is None


def test_api_v1_rejects_before_touching_the_database(
    configured_key: str,
) -> None:
    # No Postgres runs in the unit environment: a 401 (not a DB error) proves the router
    # dependency short-circuits before the route's session dependency executes.
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/facilities")
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid or missing X-API-Key header"}


def test_healthz_stays_unauthenticated(configured_key: str) -> None:
    with TestClient(create_app()) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
