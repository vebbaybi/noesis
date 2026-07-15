from __future__ import annotations

from noesis_agent.domain.contracts.analytics import AnalyticsSnapshot
from noesis_agent.infrastructure.observability.metrics import Metrics


class AnalyticsService:
    def __init__(self) -> None:
        self.metrics = Metrics()

    def record_listener_count(self, count: int) -> None:
        self.metrics.incr("listener_samples")
        self.metrics.counters["listeners_last"] = count

    def record_message_seen(self) -> None:
        self.metrics.incr("messages_seen")

    def record_reply_generated(self) -> None:
        self.metrics.incr("replies_generated")

    def snapshot_model(self) -> AnalyticsSnapshot:
        return AnalyticsSnapshot.from_counters(self.metrics.snapshot())

    def snapshot(self) -> dict:
        return self.snapshot_model().model_dump(mode="json")
