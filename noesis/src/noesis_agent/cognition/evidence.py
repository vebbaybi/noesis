from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class Evidence:
    source_type: str
    source_id: str
    scope: dict[str, str | None]
    facts: dict[str, Any]
    freshness: str = "live_event"
    confidence: float = 1.0
    authorized: bool = True
    data_classification: str = "platform_metadata"
    tool_name: str = ""
    cache_state: str = "not_cached"
    limitation: str = ""
    retrieved_at: str = ""

    def safe_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["retrieved_at"] = self.retrieved_at or datetime.now(timezone.utc).isoformat()
        return payload


__all__ = ["Evidence"]
