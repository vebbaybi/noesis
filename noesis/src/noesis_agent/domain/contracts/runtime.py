from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from noesis_agent.domain.entities.transcript import TranscriptEvent
from noesis_agent.domain.entities.types import SpeakerRole


class ResponseMode(str, Enum):
    SHORT = "short"
    DEEP = "deep"
    MODERATOR = "moderator"
    GUEST = "guest"
    SILENCE_RECOVERY = "silence_recovery"
    OFF_TOPIC_RECOVERY = "off_topic_recovery"
    SHORT_ANSWER = "short_answer"
    DEEP_ANSWER = "deep_answer"
    GUEST_REPLY = "guest_reply"
    COHOST_REPLY = "cohost_reply"
    TRANSITION = "transition"
    RECAP = "recap"
    CLOSING = "closing"
    SAFETY_REDIRECT = "safety_redirect"


class HostIntent(str, Enum):
    ANSWER_DIRECTLY = "answer_directly"
    ASK_FOLLOW_UP = "ask_follow_up"
    MOVE_TO_NEXT_TOPIC = "move_to_next_topic"
    SUMMARIZE = "summarize"
    SUMMARIZE_SEGMENT = "summarize_segment"
    MODERATE = "moderate"
    MODERATE_CONFLICT = "moderate_conflict"
    INVITE_SPEAKER = "invite_speaker"
    RECOVER_FROM_SILENCE = "recover_from_silence"
    RECOVER_SILENCE = "recover_silence"
    HANDLE_INTERRUPTION = "handle_interruption"
    PARK_TOPIC = "park_topic"
    END_SEGMENT = "end_segment"
    CLOSE_SHOW = "close_show"
    CLOSE_SESSION = "close_session"
    WAIT = "wait"


class SpeakerState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    display_name: str
    role: SpeakerRole = "audience"
    is_active: bool = False
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    speaking_seconds: float = Field(default=0.0, ge=0.0)
    interruption_count: int = Field(default=0, ge=0)
    topics: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AudienceSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    source: Literal["discord", "x", "api", "system"] = "system"
    signal_type: Literal["question", "reaction", "topic_request", "risk", "moderation"] = "reaction"
    content: str = Field(min_length=1, max_length=1000)
    weight: float = Field(default=0.5, ge=0.0, le=1.0)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_user: str | None = None


class TopicPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    angle: str = Field(default="", max_length=500)
    priority: int = Field(default=1, ge=1, le=100)
    status: Literal["queued", "active", "parked", "done"] = "queued"
    duration_goal_minutes: int | None = Field(default=None, ge=1, le=120)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    notes: list[str] = Field(default_factory=list)


class RoomState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Literal["discord", "x", "api", "web", "unknown"] = "unknown"
    status: Literal["idle", "scheduled", "live", "ending", "ended", "error"] = "idle"
    audience_size: int = Field(default=0, ge=0)
    speakers: list[SpeakerState] = Field(default_factory=list)
    active_topic: str | None = None
    energy_level: Literal["low", "steady", "high", "chaotic"] = "steady"
    silence_seconds: float = Field(default=0.0, ge=0.0)
    interruption_active: bool = False
    audience_signals: list[AudienceSignal] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    description: str = Field(min_length=1, max_length=500)
    owner: str | None = None
    source_event_id: str | None = None
    status: Literal["open", "done", "dismissed"] = "open"
    due_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    title: str
    mode: Literal["host", "cohost", "solo", "guest"] = "host"
    room: RoomState = Field(default_factory=RoomState)
    topics: list[TopicPlan] = Field(default_factory=list)
    transcript_tail: list[TranscriptEvent] = Field(default_factory=list)
    memory_refs: list[str] = Field(default_factory=list)
    current_intent: HostIntent = HostIntent.WAIT
    response_mode: ResponseMode = ResponseMode.SHORT_ANSWER
    action_items: list[ActionItem] = Field(default_factory=list)


class HostDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    intent: HostIntent
    reason: str = Field(min_length=1, max_length=500)
    should_respond: bool = True
    target_speaker: str | None = None
    topic: str | None = None
    confidence: float = Field(default=0.65, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "ActionItem",
    "AudienceSignal",
    "HostDecision",
    "HostIntent",
    "ResponseMode",
    "RoomState",
    "SessionContext",
    "SpeakerState",
    "TopicPlan",
]
