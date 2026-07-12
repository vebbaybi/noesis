from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class MentionIntent(str, Enum):
    QUESTION = "question"
    EXPLAIN = "explain"
    SUMMARIZE = "summarize"
    PROJECT_HELP = "project_help"
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"
    CONTRIBUTION_GUIDANCE = "contribution_guidance"
    CASUAL = "casual"
    HOSTILE = "hostile"
    UNCLEAR = "unclear"


class MentionEvent(BaseModel):
    event_id: str = Field(min_length=1, max_length=256)
    platform: Literal["discord", "x", "local", "unknown"] = "local"
    text: str = Field(default="", max_length=20_000)
    user_id: str | None = None
    username: str | None = None
    conversation_id: str | None = None
    channel_id: str | None = None
    parent_text: str | None = Field(default=None, max_length=20_000)
    attachments: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    mentioned: bool | None = None
    is_reply_to_noesis: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("text", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        return str(value or "").strip()


class MentionResponse(BaseModel):
    event_id: str
    status: Literal[
        "responded", "ignored", "needs_clarification", "unsupported",
        "provider_unavailable", "dry_run",
    ]
    should_respond: bool
    intent: MentionIntent
    text: str = ""
    responder: str = "none"
    reason: str = ""
    platform: str
    live_send_attempted: bool = False
    missing_capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MentionDispatchResult(BaseModel):
    platform: str
    event_id: str
    intent: MentionIntent
    response_status: str
    response_text: str = ""
    send_mode: Literal["dry_run", "disabled", "attempted", "failed", "succeeded"]
    send_attempted: bool = False
    send_result: str = ""
    disabled_reason: str = ""
    missing_credentials: list[str] = Field(default_factory=list)
