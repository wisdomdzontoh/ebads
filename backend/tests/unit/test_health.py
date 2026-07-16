"""Health endpoint smoke tests (docs/04-api-spec.md §2).

These exercise the routing and graceful-degradation behaviour without a live database:
  - ``/healthz`` is liveness-only and must always return 200.
  - ``/readyz`` must report "not ready" with 503 when the DB is unreachable, rather than
    raising — proving the readiness probe degrades cleanly (docs/04 §6).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_returns_ok() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_reports_not_ready_without_database() -> None:
    # No Postgres is running in the unit environment, so the DB probe fails and readiness
    # degrades to a 503 instead of erroring.
    with TestClient(create_app()) as client:
        response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json() == {"status": "not ready"}
