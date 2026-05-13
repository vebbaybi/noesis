from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key_id: str
    owner: str
    scopes: list[str] = Field(default_factory=list)
    status: Literal["active", "revoked", "disabled"] = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuthContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    auth_type: Literal["api_key", "session", "internal"] = "internal"
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


__all__ = ["ApiKeyIdentity", "AuthContext"]
