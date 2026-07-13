from __future__ import annotations

from pathlib import Path

from noesis_agent.memory import (
    WorkingMemory,
    EpisodicMemory,
    SemanticMemory,
    AudienceMemory,
    GuestMemory,
    MemoryIndexer,
    Retrieval,
)
from noesis_agent.memory.memory_indexer import SENSITIVE_PATTERN
from noesis_agent.store.guest_store import GuestStore
from noesis_agent.memory.sqlite_memory import ScopedMemoryStore


class MemoryService:
    def __init__(self, data_dir: Path) -> None:
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory(data_dir)
        self.semantic = SemanticMemory()
        self.audience = AudienceMemory()
        self.guests = GuestMemory(GuestStore(data_dir))
        self.indexer = MemoryIndexer(self.semantic)
        self.retrieval = Retrieval(self.semantic, self.episodic)
        self.scoped = ScopedMemoryStore(Path(data_dir) / "memory" / "noesis_memory.sqlite3")

    def index_transcript(self, session_id: str, transcript: str) -> list[str]:
        facts = self.indexer.index_transcript(transcript, session_id=session_id)
        events = self.working.tail()
        if events:
            self.episodic.append(session_id, events)
        return [fact.entry_id for fact in facts]

    def remember_if_safe(self, session_id: str, *, speaker: str, text: str) -> list[str]:
        content = text.strip()
        if not content or SENSITIVE_PATTERN.search(content):
            return []
        label = speaker.strip() or "NOESIS"
        return self.index_transcript(session_id, f"{label}: {content}")
