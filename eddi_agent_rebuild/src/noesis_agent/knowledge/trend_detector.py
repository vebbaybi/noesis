from __future__ import annotations

from collections import Counter, deque
from typing import Deque


class TrendDetector:
    """Tracks rolling topic frequencies to spot momentum."""

    def __init__(self, window: int = 200) -> None:
        self.window = window
        self.events: Deque[str] = deque(maxlen=window)

    def record(self, text: str) -> None:
        tokens = [t.lower() for t in text.split() if len(t) > 3]
        self.events.extend(tokens)

    def top(self, n: int = 5) -> list[tuple[str, int]]:
        counts = Counter(self.events)
        return counts.most_common(n)
