from __future__ import annotations


class MemoryCleaner:
    def prune(self, semantic_store, max_items: int = 1000) -> None:
        for key, facts in list(semantic_store.facts.items()):
            if len(facts) > max_items:
                semantic_store.facts[key] = facts[-max_items:]
