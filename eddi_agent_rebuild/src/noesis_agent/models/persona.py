from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from noesis_agent.models.transcript import TranscriptEvent
from noesis_agent.models.types import LengthPreset


class ToneProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=280)
    humor_temperature: float = Field(default=0.6, ge=0.0, le=1.0)
    finance_strictness: float = Field(default=0.8, ge=0.0, le=1.0)
    preferred_length: LengthPreset = "medium"


class PersonaProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    display_name: str | None = None
    default_tone: str = "sharp witty clear"
    humor_temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    finance_focus: list[str] = Field(default_factory=list)
    style_notes: list[str] = Field(default_factory=list)


class HostReplyContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    instruction: str
    latest_transcript_tail: list[TranscriptEvent] = Field(default_factory=list)
    recent_context_summary: str = ""
    current_speaker: str | None = None
    tone: str = "sharp witty clear"
    personality: str = "default"
    length_preset: LengthPreset = "medium"


class HostReplyRequest(HostReplyContext):
    latest_context: str = ""


class HostReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    speakable_text: str | None = None
    tone_used: str | None = None
    personality_used: str | None = None
    suggested_length_category: LengthPreset = "medium"
    contains_call_to_action: bool = False
    should_pin: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_response_text(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        payload = dict(value)
        if "text" not in payload and "response_text" in payload:
            payload["text"] = payload.pop("response_text")
        return payload

    @computed_field
    @property
    def response_text(self) -> str:
        return self.text


class HostReplyResponse(HostReply):
    """API response model for generated host replies."""


__all__ = [
    "HostReply",
    "HostReplyContext",
    "HostReplyRequest",
    "HostReplyResponse",
    "PersonaProfile",
    "ToneProfile",
]
