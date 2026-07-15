from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class MemoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    memory_type: Literal["episodic", "semantic", "guest"]
    content: str
    source_id: str | None = None
    score: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source_tags: list[str] = Field(default_factory=list)
    sensitive: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EpisodicMemoryRecord(MemoryEntry):
    memory_type: Literal["episodic"] = "episodic"
    session_id: str | None = None


class SemanticFact(MemoryEntry):
    memory_type: Literal["semantic"] = "semantic"
    topic: str | None = None


class GuestMemoryRecord(MemoryEntry):
    memory_type: Literal["guest"] = "guest"
    guest_handle: str | None = None


__all__ = ["EpisodicMemoryRecord", "GuestMemoryRecord", "MemoryEntry", "SemanticFact"]
