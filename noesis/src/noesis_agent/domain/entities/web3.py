from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from noesis_agent.domain.entities.types import ChainId


class TokenMention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1, max_length=24)
    name: str | None = None
    chain: ChainId = "other"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    context: str = ""


class NFTCollectionMention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    slug: str | None = None
    chain: ChainId = "ethereum"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    floor_reference: str | None = None


class MarketSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=2, max_length=120)
    stance: Literal["bullish", "bearish", "neutral", "mixed"] = "neutral"
    timeframe: str = "current"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high"] = "medium"
    evidence: list[str] = Field(default_factory=list)
    invalidation: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Web3EntityMention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: Literal["token", "protocol", "nft_collection", "chain", "wallet", "narrative"]
    value: str = Field(min_length=1, max_length=120)
    chain: ChainId | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


__all__ = [
    "MarketSignal",
    "NFTCollectionMention",
    "TokenMention",
    "Web3EntityMention",
]
