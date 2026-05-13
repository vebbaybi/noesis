from __future__ import annotations

import time


class CountdownTracker:
    def __init__(self) -> None:
        self.starts: dict[str, float] = {}

    def start(self, key: str) -> None:
        self.starts[key] = time.time()

    def elapsed(self, key: str) -> float:
        return time.time() - self.starts.get(key, time.time())
