from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class XPostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    media_urls: list[str] = Field(default_factory=list)
    reply_to_tweet_id: str | None = None
    schedule_at: datetime | None = None
    dry_run: bool = True

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        payload = dict(value)
        if "text" not in payload and "content" in payload:
            payload["text"] = payload.pop("content")
        if "reply_to_tweet_id" not in payload and "reply_to" in payload:
            payload["reply_to_tweet_id"] = payload.pop("reply_to")
        return payload


class QuickTweetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    style: Literal["alpha", "funny", "recap", "teaser"] = "recap"
    max_length: int = 240
    include_hashtags: bool = True
    dry_run: bool = True


class PlatformAnnouncement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Literal["x", "discord", "youtube", "generic"] = "generic"
    headline: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=1000)
    scheduled_at: datetime | None = None
    join_url: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


__all__ = ["PlatformAnnouncement", "QuickTweetRequest", "XPostRequest"]
