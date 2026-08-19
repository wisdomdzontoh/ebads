"""Response schema for ``GET /audit-log`` (docs/02-data-model.md §2.9, NFR8)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    entity: str
    entity_id: str
    detail: dict[str, Any]
    logged_at: datetime
