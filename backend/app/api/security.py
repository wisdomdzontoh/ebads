"""Static ``X-API-Key`` authentication for the versioned API (docs/04-api-spec.md §1).

The prototype authenticates every ``/api/v1`` request against a single static key
(``Settings.api_key``, the ``API_KEY`` environment variable) carried in the ``X-API-Key``
header. Full auth (users, roles, tokens) is explicitly out of scope (PRD §5).

``[IMPL]`` A **blank** configured key disables the check: unit/integration test runs and
bare local dev have no ``API_KEY`` set and must keep working, while the deployed stack sets
it in ``infra/.env`` and therefore enforces it. Health probes (``/healthz``/``/readyz``)
are mounted outside ``/api/v1`` and are never authenticated — liveness must not depend on
credentials.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

# auto_error=False: a missing header falls through to our 401 below (FastAPI's built-in
# error would be a 403 with a less actionable message).
_api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Static engine API key (docs/04 §1); configured via the API_KEY env var.",
)


def require_api_key(provided: Annotated[str | None, Depends(_api_key_header)]) -> None:
    """Reject the request with 401 unless it carries the configured API key.

    Constant-time comparison (``secrets.compare_digest``) so the key cannot be probed
    byte-by-byte via response timing.
    """
    expected = get_settings().api_key
    if not expected:
        return  # blank key = auth disabled (tests / bare local dev)
    if provided is None or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "invalid or missing X-API-Key header",
        )
