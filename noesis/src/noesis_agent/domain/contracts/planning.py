from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from noesis_agent.domain.entities.types import Platform, normalize_platform


class Topic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=120)
    angle: str = Field(default="", max_length=280)
    priority: int = Field(default=1, ge=1, le=100)
    duration_goal_minutes: int | None = Field(default=None, ge=2, le=45)
    speakers: list[str] | None = None


class EpisodePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    show_title: str = Field(min_length=3, max_length=140)
    platform: Platform = "dual"
    objective: str = Field(max_length=500)
    target_audience: str = Field(max_length=300)
    topics: list[Topic] = Field(min_length=1)
    duration_minutes: int = Field(default=60, ge=15, le=240)
    preferred_start_time: datetime | None = None
    hosts: list[str] = Field(default_factory=list)
    guests: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    rundown: list[dict[str, Any]] = Field(default_factory=list)
    opening_script: str = ""
    closing_script: str = ""

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform_value(cls, value: Any) -> str:
        return normalize_platform(value)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_audience(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        if "target_audience" not in payload and "audience" in payload:
            payload["target_audience"] = payload.pop("audience")
        return payload


class EpisodePlan(EpisodePlanRequest):
    model_config = ConfigDict(extra="forbid")
    plan_id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str | None = None
    version: int = 1
    active: bool = True

    @computed_field
    @property
    def short_id(self) -> str:
        return self.plan_id[:8]

    @computed_field
    @property
    def audience(self) -> str:
        return self.target_audience


__all__ = ["EpisodePlan", "EpisodePlanRequest", "Topic"]
