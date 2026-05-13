from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: uuid4().hex)
    event_type: str
    source: str = "system"
    session_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    severity: Literal["debug", "info", "warning", "error"] = "info"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionLifecycleEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    action: Literal["created", "started", "ended", "failed"]
    title: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = ["EventEnvelope", "SessionLifecycleEvent"]
