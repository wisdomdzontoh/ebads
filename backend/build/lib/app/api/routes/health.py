"""Liveness and readiness endpoints (docs/04-api-spec.md §2).

These live at the application root (not under ``/api/v1``) so orchestration and the
RB-1 runbook can probe them directly:
  - ``GET /healthz`` — liveness: the process is up and serving.
  - ``GET /readyz``  — readiness: the database is reachable (else 503).
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.db.session import check_database_ready

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Report process liveness. Always 200 while the app is serving."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(response: Response) -> dict[str, str]:
    """Report readiness based on database reachability (docs/13-runbooks.md RB-1).

    Returns ``{"status": "ready"}`` with 200 when the DB answers, otherwise
    ``{"status": "not ready"}`` with 503 so callers can distinguish "up" from "usable".
    """
    if await check_database_ready():
        return {"status": "ready"}
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "not ready"}
