"""Audit logging — every create/modify/approve, attributable to an account (NFR8).

A thin insert helper shared by every mutating service so ``audit_log`` rows are written
consistently rather than each service inventing its own shape.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog


async def record(
    session: AsyncSession,
    user_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: uuid.UUID | str,
    detail: dict[str, Any] | None = None,
) -> None:
    """Add an ``audit_log`` row to ``session`` (does not commit — caller owns the transaction).

    ``user_id`` is ``None`` only for adapter-originated writes (docs/02 §3.9); every route
    added in this increment has an authenticated actor and must pass one.
    """
    session.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=str(entity_id),
            detail=detail or {},
        )
    )
