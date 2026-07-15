from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class MemoryCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(default_factory=lambda: uuid4().hex)
    tenant_id: str = Field(min_length=1, max_length=200)
    user_id: str = Field(min_length=1, max_length=200)
    subject: str = Field(min_length=2, max_length=120)
    correction: str = Field(min_length=2, max_length=1500)
    reason: str = Field(default="", max_length=500)
    correlation_id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MemoryCorrectionRecord(MemoryCorrectionRequest):
    status: str = Field(default="pending_review", pattern=r"^(pending_review|accepted|rejected)$")
    moderation_decision_id: str
