from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from noesis_agent.models.cognition import ResponseRoute
from noesis_agent.models.runtime import AudienceSignal, HostDecision, HostIntent, ResponseMode
from noesis_agent.models.session import SessionState
from noesis_agent.models.transcript import TranscriptEvent
from noesis_agent.models.types import SpeakerRole


class LiveEventType(str, Enum):
    USER_MESSAGE = "user_message"
    HOST_MESSAGE = "host_message"
    SPEAKER_JOINED = "speaker_joined"
    SPEAKER_LEFT = "speaker_left"
    AUDIENCE_QUESTION = "audience_question"
    INTERRUPTION = "interruption"
    SILENCE_DETECTED = "silence_detected"
    TOPIC_CHANGE = "topic_change"
    MODERATION_SIGNAL = "moderation_signal"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"


class LiveSessionEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    event_type: LiveEventType
    speaker: str | None = None
    role: SpeakerRole = "audience"
    content: str = Field(default="", max_length=4000)
    platform: Literal["x", "discord", "both"] = "both"
    topic: str | None = Field(default=None, max_length=160)
    audience_signal: AudienceSignal | None = None
    silence_seconds: float = Field(default=0.0, ge=0.0)
    interrupted_speaker: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_content_for_message_events(self) -> "LiveSessionEventRequest":
        message_events = {
            LiveEventType.USER_MESSAGE,
            LiveEventType.HOST_MESSAGE,
            LiveEventType.AUDIENCE_QUESTION,
            LiveEventType.INTERRUPTION,
            LiveEventType.MODERATION_SIGNAL,
            LiveEventType.TOPIC_CHANGE,
        }
        if self.event_type in message_events and not (self.content.strip() or self.topic):
            raise ValueError(f"{self.event_type.value} requires content or topic")
        return self


class LiveEventIngestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_state: SessionState
    decision: HostDecision
    response_route: ResponseRoute | None = None
    transcript_event: TranscriptEvent | None = None
    memory_updated: bool = False


class OutputChannel(str, Enum):
    LOCAL_TEXT = "local_text"
    DISCORD_TEXT = "discord_text"
    DISCORD_VOICE = "discord_voice"
    API_RESPONSE_ONLY = "api_response_only"


class OutputStatus(str, Enum):
    SENT = "sent"
    SKIPPED = "skipped"
    DISABLED = "disabled"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class HostOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    session_id: str
    text: str = Field(min_length=1, max_length=8000)
    channels: list[OutputChannel] = Field(default_factory=lambda: [OutputChannel.API_RESPONSE_ONLY])
    response_mode: ResponseMode | None = None
    host_intent: HostIntent | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OutputDispatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: OutputChannel
    status: OutputStatus
    adapter_name: str
    message: str = Field(default="", max_length=1000)
    output_id: str | None = None
    external_id: str | None = None
    error: str | None = Field(default=None, max_length=1000)
    delivered_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HostTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: LiveSessionEventRequest
    output_channels: list[OutputChannel] = Field(default_factory=list)
    generate_response: bool = True
    allow_deterministic_fallback: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class HostTurnResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    ingested_event_id: str
    host_intent: HostIntent
    response_mode: ResponseMode | None = None
    cognition_provider_used: str | None = None
    host_text: str = ""
    transcript_event_id: str | None = None
    memory_write_ids: list[str] = Field(default_factory=list)
    dispatch_results: list[OutputDispatchResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    ingestion: LiveEventIngestionResult
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


__all__ = [
    "HostOutput",
    "HostTurnRequest",
    "HostTurnResult",
    "LiveEventIngestionResult",
    "LiveEventType",
    "LiveSessionEventRequest",
    "OutputChannel",
    "OutputDispatchResult",
    "OutputStatus",
]
