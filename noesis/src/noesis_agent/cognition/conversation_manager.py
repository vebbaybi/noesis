from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Iterable, List

from noesis_agent.audio.transcription import TranscriptSegment
from noesis_agent.cognition.topic_graph import TopicGraph
from noesis_agent.models.schemas import TranscriptEvent, TranscriptEventType
from noesis_agent.utils.noesislogger import NoesisLogger


@dataclass
class ConversationState:
    session_id: str
    last_speaker: str | None = None
    transcript_tail: list[TranscriptEvent] = field(default_factory=list)
    current_topic: str | None = None


class ConversationManager:
    """Maintains rolling transcript, speaker activity, and topic graph."""

    def __init__(self, window: int = 50) -> None:
        self.logger = NoesisLogger("noesis.cognition.conversation_manager").logger
        self.window = window
        self.events: Deque[TranscriptEvent] = deque(maxlen=window)
        self.topic_graph = TopicGraph()
        self.active_speakers: Deque[str] = deque(maxlen=6)
        self.lock = asyncio.Lock()

    async def ingest_segments(
        self,
        session_id: str,
        segments: list[TranscriptSegment],
        speaker: str | None = None,
        platform: str = "discord",
    ) -> list[TranscriptEvent]:
        """Convert raw segments into structured transcript events and update state."""
        async with self.lock:
            events: list[TranscriptEvent] = []
            for seg in segments:
                event = TranscriptEvent(
                    session_id=session_id,
                    speaker=speaker or seg.speaker or "unknown",
                    content=seg.text,
                    platform=platform,
                    event_type=TranscriptEventType.MESSAGE,
                )
                self.events.append(event)
                events.append(event)
                self._update_topics(event.content)
                self._update_speakers(event.speaker)
            if events:
                self.logger.log_transcript(
                    session_id=session_id,
                    speaker=events[-1].speaker or "unknown",
                    text="\n".join(e.content for e in events),
                    room_id=platform,
                )
            return events

    def _update_topics(self, content: str) -> None:
        # Simple heuristic: use first 6 words as a topic key
        topic = " ".join(content.split()[:6]).lower()
        previous = self.topic_graph.hottest_topics(1)[0] if self.topic_graph.graph else None
        self.topic_graph.add_transition(previous, topic)

    def _update_speakers(self, speaker: str | None) -> None:
        if speaker:
            self.active_speakers.append(speaker)

    def recent_transcript(self, limit: int = 12) -> str:
        tail = list(self.events)[-limit:]
        return "\n".join(f"{e.speaker}: {e.content}" for e in tail)

    def current_topics(self, limit: int = 5) -> list[str]:
        return self.topic_graph.hottest_topics(limit)

    def unresolved_threads(self, limit: int = 3) -> list[str]:
        return self.topic_graph.unresolved_threads(limit)


__all__ = ["ConversationManager", "ConversationState"]
