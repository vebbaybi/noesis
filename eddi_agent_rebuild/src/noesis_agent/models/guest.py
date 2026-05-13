from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Guest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handle: str = Field(min_length=2, max_length=80)
    display_name: str | None = None
    bio: str | None = None
    expertise: list[str] = Field(default_factory=list)
    finance_focus: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    prior_appearances: int = 0
    last_seen: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    humor_profile: str | None = None


__all__ = ["Guest"]
