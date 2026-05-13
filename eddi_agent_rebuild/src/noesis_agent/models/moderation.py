from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ModerationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: str
    text: str
    decision: Literal["allow", "warn", "mute", "remove"] = "allow"
    reason: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ModerationQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report: ModerationReport
    status: Literal["pending", "reviewed", "resolved"] = "pending"
    assigned_to: str | None = None


__all__ = ["ModerationQueueItem", "ModerationReport"]
