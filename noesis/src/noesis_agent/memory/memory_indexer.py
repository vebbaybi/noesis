from __future__ import annotations

import re
from sklearn.feature_extraction.text import TfidfVectorizer
from noesis_agent.domain.entities.memory import SemanticFact
from noesis_agent.memory.semantic_memory import SemanticMemory


SENSITIVE_PATTERN = re.compile(
    r"(?i)(api[_ -]?key|token|password|secret|private[_ -]?key|seed phrase|bearer\s+[a-z0-9._-]+)"
)


class MemoryIndexer:
    def __init__(self, semantic: SemanticMemory) -> None:
        self.semantic = semantic

    @staticmethod
    def _features(text: str) -> tuple[list[str], list[str]]:
        """Extract index terms without coupling storage to the cognition layer."""
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=12)
        try:
            matrix = vectorizer.fit_transform([text])
        except ValueError:
            return [], []
        names = vectorizer.get_feature_names_out()
        scores = matrix.toarray()[0]
        ranked = [str(names[index]) for index in scores.argsort()[::-1] if scores[index] > 0]
        keywords = [term for term in ranked if " " not in term][:6]
        keywords.extend(term for term in ranked if " " in term and term not in keywords)
        entities = re.findall(r"(?:\$[A-Za-z]{2,10}\b|\b[A-Z]{2,8}\b)", text)
        return keywords, [entity.casefold() for entity in entities]

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

            keywords, entities = self._features(cleaned)
            for keyword in keywords[:4]:
                facts.append(
                    self.semantic.add(keyword, cleaned, confidence=0.6, source_id=session_id, source_tags=source_tags)
                )
            for entity in entities[:4]:
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
