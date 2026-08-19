"""Request/response schemas for ``/auth`` (EBADS_PRD.md §10)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field

from app.parameters import MIN_PASSWORD_LENGTH, Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Body of ``POST /auth/login`` (EBADS_PRD.md §10)."""

    access_token: str
    refresh_token: str
    role: Role
    facility_id: uuid.UUID | None


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str


class PasswordChangeRequest(BaseModel):
    """Body of ``PATCH /auth/password`` — self-service, the caller's own account only."""

    current_password: str
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH)
