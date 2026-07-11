from __future__ import annotations


class Metrics:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    def incr(self, name: str, value: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + value

    def snapshot(self) -> dict[str, int]:
        return dict(self.counters)
