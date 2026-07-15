from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class XEventContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    event_type: Literal["mention", "reply", "quote", "public_post"]
    conversation_id: str | None = None
    author_id: str | None = None
    referenced_post_ids: list[str] = Field(default_factory=list, max_length=20)
    intent_class: Literal["research", "content", "moderation", "scam_signal",
                          "project_intelligence", "conversation"] = "conversation"


class SpaceEventContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    space_id: str
    event_id: str
    event_type: Literal["lifecycle", "speaker_turn", "transcript_segment", "question", "answer",
                        "commitment", "decision", "fact_check", "moderation", "action_item",
                        "post_space_summary"]
    participant_role: Literal["host", "cohost", "speaker", "listener", "unknown"] = "unknown"
    participant_id: str | None = None
    text: str = Field(default="", max_length=20_000)


__all__ = ["SpaceEventContract", "XEventContract"]
