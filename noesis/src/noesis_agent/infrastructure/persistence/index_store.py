from __future__ import annotations

from noesis_agent.domain.contracts.indexing import IndexingState, SemanticSourceRecord
from noesis_agent.infrastructure.persistence.json_store import JsonStore


class JsonSemanticSourceRepository:
    def __init__(self, store: JsonStore) -> None:
        self._store = store

    def save_source(self, record: SemanticSourceRecord) -> None:
        self._store.write("semantic_sources", record.source_id, record.model_dump(mode="json"))

    def get_source(self, source_id: str) -> SemanticSourceRecord | None:
        payload = self._store.read("semantic_sources", source_id)
        return SemanticSourceRecord.model_validate(payload) if payload is not None else None

    def list_sources(self, tenant_id: str | None = None) -> list[SemanticSourceRecord]:
        records = [SemanticSourceRecord.model_validate(item) for item in self._store.list("semantic_sources")]
        return [item for item in records if tenant_id is None or item.tenant_id == tenant_id]

    def save_state(self, state: IndexingState) -> None:
        self._store.write("semantic_index_state", state.source_id, state.model_dump(mode="json"))

    def get_state(self, source_id: str) -> IndexingState | None:
        payload = self._store.read("semantic_index_state", source_id)
        return IndexingState.model_validate(payload) if payload is not None else None

    def failed_states(self, tenant_id: str | None = None) -> list[IndexingState]:
        states = [IndexingState.model_validate(item) for item in self._store.list("semantic_index_state")]
        return [item for item in states if item.failure_category is not None
                and (tenant_id is None or item.tenant_id == tenant_id)]
