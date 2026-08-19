"""Request/response schemas for ``/users`` (docs/02-data-model.md §2.3)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.parameters import MIN_PASSWORD_LENGTH, Role, UserStatus


class UserCreate(BaseModel):
    """Body of ``POST /api/v1/users``.

    ``facility_id`` is honoured only when the caller is system_administrator; a
    facility_administrator's new accounts are always pinned to their own facility
    regardless of what is sent here (``domain/users/service.py``).
    """

    email: EmailStr
    # Matches app/security/passwords.py::hash_password's own floor, enforced here too so a
    # too-short password 422s cleanly instead of reaching the service as an unhandled
    # PasswordTooShortError (docs/09-parameters.md §10).
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)
    role: Role
    facility_id: uuid.UUID | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: Role
    facility_id: uuid.UUID | None
    status: UserStatus
    created_at: datetime
    last_login_at: datetime | None

    @field_validator("role", mode="before")
    @classmethod
    def _role_from_relationship(cls, value: object) -> object:
        """``UserAccount.role`` is the joined ``Role`` row, not a bare enum — unwrap ``.name``."""
        return getattr(value, "name", value)
