from __future__ import annotations

from collections import deque, Counter


class SpamDetector:
    """Detects repeated messages or link spam."""

    def __init__(self, window: int = 50) -> None:
        self.window = deque(maxlen=window)

    def is_spam(self, speaker: str, text: str) -> bool:
        key = (speaker, text.strip().lower())
        self.window.append(key)
        counts = Counter(self.window)
        if counts[key] >= 3:
            return True
        if text.count("http") >= 3:
            return True
        return False
