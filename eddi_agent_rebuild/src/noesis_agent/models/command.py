from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CommandIntent(str, Enum):
    ANNOUNCE = "announce"
    PLAN_EPISODE = "plan_episode"
    START_SOLO = "start_solo"
    NFT_INSIGHT = "nft_insight"
    UNKNOWN = "unknown"


class ParsedCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: CommandIntent = CommandIntent.UNKNOWN
    raw_input: str = ""
    args: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str = "system"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CommandExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: CommandIntent = CommandIntent.UNKNOWN
    ok: bool = True
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


__all__ = ["CommandExecutionResult", "CommandIntent", "ParsedCommand"]
