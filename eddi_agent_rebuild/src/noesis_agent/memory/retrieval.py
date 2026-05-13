from __future__ import annotations

from noesis_agent.memory.semantic_memory import SemanticMemory
from noesis_agent.memory.episodic_memory import EpisodicMemory


class Retrieval:
    def __init__(self, semantic: SemanticMemory, episodic: EpisodicMemory) -> None:
        self.semantic = semantic
        self.episodic = episodic

    def recall(self, topic: str) -> list[str]:
        return self.semantic.search(topic)
