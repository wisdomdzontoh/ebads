"""Request/response schemas for ``/auth`` (EBADS_PRD.md §10)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr

from app.parameters import Role


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
