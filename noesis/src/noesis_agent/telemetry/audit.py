from __future__ import annotations


class AuditLog:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def record(self, action: str, **meta) -> None:
        self.events.append({"action": action, **meta})

    def tail(self, n: int = 20) -> list[dict]:
        return self.events[-n:]
