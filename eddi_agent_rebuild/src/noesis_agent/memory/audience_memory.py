from __future__ import annotations

from collections import defaultdict
from datetime import datetime


class AudienceMemory:
    def __init__(self) -> None:
        self.records: defaultdict[str, dict] = defaultdict(dict)

    def update(self, handle: str, note: str) -> None:
        self.records[handle]["note"] = note
        self.records[handle]["last_seen"] = datetime.utcnow().isoformat()

    def get(self, handle: str) -> dict | None:
        return self.records.get(handle)
