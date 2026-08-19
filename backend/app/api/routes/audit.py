"""Audit log read endpoint (docs/02 §2.9, NFR8). system_administrator only."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.audit import AuditLogRead
from app.db.models.audit_log import AuditLog
from app.db.models.user_account import UserAccount
from app.db.session import get_session
from app.parameters import PermissionAction
from app.security.dependencies import require_permission

router = APIRouter(prefix="/audit-log", tags=["audit"])

ReaderDep = Annotated[UserAccount, Depends(require_permission("audit_log", PermissionAction.READ))]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[AuditLogRead])
async def list_audit_log(
    session: SessionDep,
    _reader: ReaderDep,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
) -> list[AuditLogRead]:
    """List audit entries, newest first; optionally bounded by ``from``/``to``."""
    query = select(AuditLog).order_by(AuditLog.logged_at.desc())
    if from_ is not None:
        query = query.where(AuditLog.logged_at >= from_)
    if to is not None:
        query = query.where(AuditLog.logged_at <= to)
    records = (await session.scalars(query)).all()
    return [AuditLogRead.model_validate(r) for r in records]
