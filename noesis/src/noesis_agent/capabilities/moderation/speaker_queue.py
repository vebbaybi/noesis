from __future__ import annotations

from collections import deque


class SpeakerQueue:
    """Maintains a FIFO queue of speakers requesting the mic."""

    def __init__(self) -> None:
        self.queue: deque[str] = deque()

    def request(self, speaker: str) -> None:
        if speaker not in self.queue:
            self.queue.append(speaker)

    def pop_next(self) -> str | None:
        return self.queue.popleft() if self.queue else None

    def list(self) -> list[str]:
        return list(self.queue)
