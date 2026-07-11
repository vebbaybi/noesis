from __future__ import annotations

from collections import deque
from typing import Deque
from noesis_agent.utils.noesislogger import NoesisLogger
from noesis_agent.models.schemas import TranscriptEvent


class WorkingMemory:
    """Short-lived rolling buffer of transcript events for rapid recall."""

    def __init__(self, max_events: int = 200) -> None:
        self.logger = NoesisLogger(
            logger_name="noesis_agent.memory.working_memory",
        ).logger
        self.events: Deque[TranscriptEvent] = deque(maxlen=max_events)

    def add(self, events: list[TranscriptEvent]) -> None:
        for event in events:
            self.events.append(event)

    def tail(self, n: int = 20) -> list[TranscriptEvent]:
        return list(self.events)[-n:]

    def save_memory(self, events: list[TranscriptEvent]) -> None:
        self.add(events)
        self.logger.info("Noesis memory has been updated")

    def clear_memory(self) -> None:
        self.events.clear()
        self.logger.info("Noesis working memory has been cleared")
