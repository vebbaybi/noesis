from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from noesis_agent.domain.entities.memory import SemanticFact


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
        candidates = [record for records in self.facts.values() for record in records if not record.sensitive]
        if not candidates or not topic.strip():
            return []
        documents = [f"{record.topic} {record.content}" for record in candidates]
        matrix = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True).fit_transform([topic, *documents])
        similarities = cosine_similarity(matrix[0:1], matrix[1:]).ravel()
        scored = sorted(
            zip(candidates, similarities),
            key=lambda pair: (float(pair[1]) * 0.8 + pair[0].confidence * 0.2,
                              pair[0].created_at),
            reverse=True,
        )
        # Exact topic lookup remains useful even for short opaque identifiers;
        # semantic queries require a non-zero lexical/phrase relationship.
        return [record for record, score in scored
                if score > 0.0 or record.topic.casefold() == topic.casefold()][:limit]
