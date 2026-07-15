from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_serializer, field_validator, model_validator

from noesis_agent.domain.contracts.runtime import RoomState, TopicPlan
from noesis_agent.domain.entities.transcript import TranscriptEvent
from noesis_agent.domain.entities.types import Platform, normalize_platform


class SessionPlatformState(BaseModel):
    """Per-platform runtime state used when a room spans X and Discord."""

    model_config = ConfigDict(extra="forbid")

    platform: Literal["x", "discord"]
    status: Literal["pending", "live", "ended", "error"] = "pending"
    external_id: str | None = None
    join_url: str | None = None
    recording_url: str | None = None
    recording_status: Literal["none", "active", "completed", "failed"] = "none"
    started_at: datetime | None = None
    ended_at: datetime | None = None
    participant_count: int = 0
    last_heartbeat: datetime | None = None


class Session(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(default_factory=lambda: uuid4().hex)
    plan_id: str
    title: str
    mode: Literal["host", "cohost", "solo", "guest"] = "host"
    platforms: list[SessionPlatformState] = Field(min_length=1)
    status: Literal["created", "scheduled", "live", "ended", "cancelled", "failed"] = "created"
    started_at: datetime | None = None
    ended_at: datetime | None = None
    hosts: list[str] = Field(default_factory=list)
    guests: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_seconds: int | None = None
    room_state: RoomState = Field(default_factory=RoomState)
    topic_plan: list[TopicPlan] = Field(default_factory=list)

    @computed_field
    @property
    def primary_platform(self) -> str:
        return self.platforms[0].platform if self.platforms else "unknown"

    @field_serializer("platforms")
    def sort_platforms(self, platforms: list[SessionPlatformState], _info):
        return sorted(platforms, key=lambda item: (item.platform != "x", item.platform))


class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    title: str | None = None
    platforms: list[Literal["x", "discord"]] = Field(default_factory=lambda: ["x", "discord"])
    mode: Literal["host", "cohost", "solo", "guest"] = "host"
    hosts: list[str] = Field(default_factory=list)
    guests: list[str] = Field(default_factory=list)
    scheduled_start: datetime | None = None

    @field_validator("platforms", mode="before")
    @classmethod
    def normalize_platforms(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            normalized = normalize_platform(value)
            return ["x", "discord"] if normalized == "dual" else [normalized]
        if isinstance(value, list):
            normalized_platforms = [normalize_platform(item) for item in value]
            if "dual" in normalized_platforms:
                return ["x", "discord"]
            return normalized_platforms
        raise ValueError("platforms must be str or list[str]")

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_platform_field(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        payload = dict(value)
        if "platforms" not in payload and "platform" in payload:
            payload["platforms"] = payload.pop("platform")
        return payload


class SessionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session: Session
    transcript: list[TranscriptEvent] = Field(default_factory=list)
    active_speakers: list[str] = Field(default_factory=list)
    last_speaker: str | None = None
    current_topic_index: int | None = None
    moderation_events: list[dict[str, Any]] = Field(default_factory=list)

    @computed_field
    @property
    def session_id(self) -> str:
        return self.session.session_id

    @computed_field
    @property
    def status(self) -> str:
        return self.session.status

    @computed_field
    @property
    def title(self) -> str:
        return self.session.title


__all__ = [
    "Platform",
    "Session",
    "SessionCreateRequest",
    "SessionPlatformState",
    "SessionState",
]
