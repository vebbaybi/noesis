from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from noesis_agent.models.runtime import ActionItem


class MediaAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    asset_type: Literal["audio", "video", "image", "clip", "document"] = "audio"
    path: str
    platform: Literal["local", "x", "discord", "youtube", "other"] = "local"
    duration_seconds: float | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClipMarker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=120)
    timestamp_seconds: float = Field(ge=0.0)
    note: str = ""


class PublishingManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    headline: str
    thread_posts: list[str] = Field(default_factory=list)
    discord_recap: str = ""
    media_assets: list[MediaAsset] = Field(default_factory=list)
    clip_markers: list[ClipMarker] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    plan_id: str | None = None
    headline: str = Field(max_length=140)
    key_moments: list[str] = Field(default_factory=list)
    alpha_drops: list[str] = Field(default_factory=list)
    funny_moments: list[str] = Field(default_factory=list)
    x_thread: list[str] = Field(default_factory=list)
    discord_recap: str = ""
    twitter_spaces_recap: str | None = None
    next_episode_ideas: list[str] = Field(default_factory=list)
    total_duration_seconds: int | None = None
    peak_participants: int | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_key_points(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        payload = dict(value)
        if "key_moments" not in payload and "key_points" in payload:
            payload["key_moments"] = payload.pop("key_points")
        return payload

    def to_manifest(self) -> PublishingManifest:
        return PublishingManifest(
            session_id=self.session_id,
            headline=self.headline,
            thread_posts=list(self.x_thread),
            discord_recap=self.discord_recap,
            tags=["noesis", "session-recap"],
        )


class PostShowArtifacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    summary: SessionSummary
    highlights: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    notable_audience_questions: list[str] = Field(default_factory=list)
    follow_up_ideas: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


__all__ = [
    "ClipMarker",
    "MediaAsset",
    "PostShowArtifacts",
    "PublishingManifest",
    "SessionSummary",
]
