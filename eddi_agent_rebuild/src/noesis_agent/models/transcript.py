from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from noesis_agent.models.types import SpeakerRole
from noesis_agent.models.web3 import Web3EntityMention


class TranscriptEventType(str, Enum):
    MESSAGE = "message"
    QUESTION = "question"
    ANSWER = "answer"
    ROAST = "roast"
    SHILL_CALL = "shill_call"
    MOD_ACTION = "mod_action"
    SYSTEM = "system"
    EMOJI_REACTION = "emoji_reaction"
    CLIP_MARKER = "clip_marker"


class TranscriptSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    humor_score: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_flags: list[str] = Field(default_factory=list)
    web3_mentions: list[Web3EntityMention] = Field(default_factory=list)
    sentiment: Literal["positive", "negative", "neutral", "mixed"] = "neutral"


class TranscriptEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    session_id: str
    speaker: str | None = None
    role: SpeakerRole = "audience"
    event_type: TranscriptEventType = TranscriptEventType.MESSAGE
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    platform: Literal["x", "discord", "both"] = "both"
    metadata: dict[str, Any] = Field(default_factory=dict)
    hidden: bool = False
    signals: TranscriptSignal | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        payload = dict(value)
        if "content" not in payload and "text" in payload:
            payload["content"] = payload.pop("text")

        legacy_source = payload.pop("source", None)
        if legacy_source and "role" not in payload:
            normalized_role = str(legacy_source).strip().lower()
            if normalized_role in {"host", "cohost", "guest", "audience", "system", "bot"}:
                payload["role"] = normalized_role

        return payload

    @computed_field
    @property
    def text(self) -> str:
        return self.content


class SessionTranscriptEvent(TranscriptEvent):
    """API convenience model where the session id can be path-derived."""

    session_id: str = ""


__all__ = [
    "SessionTranscriptEvent",
    "TranscriptEvent",
    "TranscriptEventType",
    "TranscriptSignal",
]
