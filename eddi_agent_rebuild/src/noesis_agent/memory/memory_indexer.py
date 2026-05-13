from __future__ import annotations

import re

from noesis_agent.brain.nlp_engine import LocalNLPEngine
from noesis_agent.models.memory import SemanticFact
from noesis_agent.memory.semantic_memory import SemanticMemory


SENSITIVE_PATTERN = re.compile(
    r"(?i)(api[_ -]?key|token|password|secret|private[_ -]?key|seed phrase|bearer\s+[a-z0-9._-]+)"
)


class MemoryIndexer:
    def __init__(self, semantic: SemanticMemory) -> None:
        self.semantic = semantic
        self.nlp = LocalNLPEngine()

    def index_transcript(self, transcript: str, *, session_id: str | None = None) -> list[SemanticFact]:
        facts: list[SemanticFact] = []
        for line in transcript.splitlines():
            if ":" in line:
                _, content = line.split(":", 1)
            else:
                content = line
            cleaned = content.strip()
            if not cleaned:
                continue

            sensitive = bool(SENSITIVE_PATTERN.search(cleaned))
            if sensitive:
                continue

            source_tags = ["transcript"]
            if session_id:
                source_tags.append(f"session:{session_id}")

            facts.append(
                self.semantic.add("general", cleaned, confidence=0.55, source_id=session_id, source_tags=source_tags)
            )

            analysis = self.nlp.analyze(cleaned)
            for keyword in analysis.keywords[:4]:
                facts.append(
                    self.semantic.add(keyword, cleaned, confidence=0.6, source_id=session_id, source_tags=source_tags)
                )
            for entity in analysis.finance_entities[:4]:
                facts.append(
                    self.semantic.add(
                        entity.lower(),
                        cleaned,
                        confidence=0.68,
                        source_id=session_id,
                        source_tags=source_tags,
                    )
                )
            for entity in analysis.web3_entities[:4]:
                facts.append(
                    self.semantic.add(
                        entity.lower(),
                        cleaned,
                        confidence=0.68,
                        source_id=session_id,
                        source_tags=source_tags,
                    )
                )
        return facts
