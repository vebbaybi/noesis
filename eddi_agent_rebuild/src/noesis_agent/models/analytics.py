from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


class LatencyMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    milliseconds: float = Field(ge=0.0)


class TokenUsageSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class EngagementSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listeners_last: int = 0
    listener_samples: int = 0
    messages_seen: int = 0
    replies_generated: int = 0


class AnalyticsSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    engagement: EngagementSnapshot = Field(default_factory=EngagementSnapshot)
    usage: TokenUsageSnapshot = Field(default_factory=TokenUsageSnapshot)
    latencies: list[LatencyMetric] = Field(default_factory=list)
    counters: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def from_counters(cls, counters: dict[str, int]) -> "AnalyticsSnapshot":
        engagement = EngagementSnapshot(
            listeners_last=int(counters.get("listeners_last", 0)),
            listener_samples=int(counters.get("listener_samples", 0)),
            messages_seen=int(counters.get("messages_seen", 0)),
            replies_generated=int(counters.get("replies_generated", 0)),
        )
        usage = TokenUsageSnapshot(
            prompt_tokens=int(counters.get("prompt_tokens", 0)),
            completion_tokens=int(counters.get("completion_tokens", 0)),
            total_tokens=int(counters.get("total_tokens", 0)),
        )
        return cls(engagement=engagement, usage=usage, counters=dict(counters))


__all__ = [
    "AnalyticsSnapshot",
    "EngagementSnapshot",
    "LatencyMetric",
    "TokenUsageSnapshot",
]
