from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from noesis_agent.models.memory import SemanticFact


class SemanticMemory:
    """Structured in-memory semantic memory for live-session recall."""

    def __init__(self) -> None:
        self.facts: defaultdict[str, list[SemanticFact]] = defaultdict(list)

    def add(
        self,
        topic: str,
        fact: str,
        *,
        confidence: float = 0.55,
        source_id: str | None = None,
        source_tags: list[str] | None = None,
        sensitive: bool = False,
    ) -> SemanticFact:
        record = SemanticFact(
            topic=topic,
            content=fact.strip(),
            source_id=source_id,
            confidence=confidence,
            score=confidence,
            source_tags=source_tags or [],
            sensitive=sensitive,
            updated_at=datetime.now(timezone.utc),
        )
        self.facts[topic].append(record)
        return record

    def search(self, topic: str, limit: int = 5) -> list[str]:
        records = sorted(
            self.facts.get(topic, []),
            key=lambda item: (item.confidence, item.created_at),
            reverse=True,
        )
        return [record.content for record in records if not record.sensitive][:limit]

    def search_records(self, topic: str, limit: int = 5) -> list[SemanticFact]:
        records = sorted(
            self.facts.get(topic, []),
            key=lambda item: (item.confidence, item.created_at),
            reverse=True,
        )
        return [record for record in records if not record.sensitive][:limit]
