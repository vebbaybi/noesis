from __future__ import annotations

from noesis_agent.domain.contracts.components import ComponentState, PersistentComponent
from noesis_agent.infrastructure.persistence.json_store import JsonStore


class JsonComponentRepository:
    _NAMESPACE = "persistent_components"

    def __init__(self, store: JsonStore) -> None:
        self._store = store

    def save(self, component: PersistentComponent) -> None:
        self._store.write(self._NAMESPACE, component.component_id, component.model_dump(mode="json"))

    def get(self, component_id: str) -> PersistentComponent | None:
        payload = self._store.read(self._NAMESPACE, component_id)
        return PersistentComponent.model_validate(payload) if payload is not None else None

    def pending(self) -> list[PersistentComponent]:
        return [component for payload in self._store.list(self._NAMESPACE)
                if (component := PersistentComponent.model_validate(payload)).state is ComponentState.PENDING]
