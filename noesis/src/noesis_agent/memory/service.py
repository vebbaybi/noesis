from __future__ import annotations

from pathlib import Path

from noesis_agent.memory.working_memory import WorkingMemory
from noesis_agent.memory.episodic_memory import EpisodicMemory
from noesis_agent.memory.semantic_memory import SemanticMemory
from noesis_agent.memory.audience_memory import AudienceMemory
from noesis_agent.memory.guest_memory import GuestMemory
from noesis_agent.memory.memory_indexer import MemoryIndexer
from noesis_agent.memory.retrieval import Retrieval
from noesis_agent.memory.memory_indexer import SENSITIVE_PATTERN
from noesis_agent.infrastructure.persistence.guest_store import GuestStore
from noesis_agent.memory.sqlite_memory import ScopedMemoryStore
from noesis_agent.memory.autonomous import AutonomousMemoryService
from noesis_agent.infrastructure.config.settings import settings


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
        self.scoped.run_hygiene()
        self.autonomous = AutonomousMemoryService(
            self.scoped, queue_size=settings.memory_queue_size,
            worker_count=settings.memory_worker_count,
            timeout=max(settings.memory_write_timeout_seconds, settings.memory_retrieval_timeout_seconds),
            max_candidates=settings.memory_max_candidates_per_event,
            confidence_threshold=settings.memory_confidence_threshold,
            importance_threshold=settings.memory_importance_threshold,
            actionability_threshold=settings.memory_actionability_threshold,
            extraction_enabled=settings.memory_candidate_extraction_enabled,
        )

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

    def recall(self, query: str, *, session_id: str | None = None, limit: int = 6) -> list[str]:
        """Authoritative cross-store recall used by cognition and application services."""
        candidates = [record.content for record in self.semantic.search_records(query, limit=limit * 2)]
        if session_id:
            candidates.extend(event.content for event in self.episodic.load(session_id))
        query_terms = {term.casefold() for term in query.split() if len(term) > 2}
        ranked = sorted(
            candidates,
            key=lambda content: len(query_terms & {term.casefold().strip(".,!?;:")
                                                    for term in content.split()}),
            reverse=True,
        )
        results: list[str] = []
        seen: set[str] = set()
        for content in ranked:
            key = content.strip().casefold()
            if key and key not in seen:
                seen.add(key)
                results.append(content.strip())
            if len(results) >= limit:
                break
        return results

    def health(self) -> dict:
        return {"store": self.scoped.health(), "worker": self.autonomous.health()}

    def diagnostics(self) -> dict:
        return self.scoped.memory_diagnostics()

    def run_hygiene(self) -> dict:
        return self.scoped.run_hygiene()

    def operator_summary(self, *, preview_limit: int = 20) -> dict:
        return {**self.scoped.operator_summary(preview_limit=preview_limit),
                "worker": self.autonomous.health()}
