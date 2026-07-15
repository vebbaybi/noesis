from __future__ import annotations

from pathlib import Path

from noesis_agent.domain.entities.guest import Guest
from noesis_agent.infrastructure.persistence.json_store import JsonStore


class GuestStore:
    def __init__(self, data_dir: Path) -> None:
        self.store = JsonStore(data_dir / "guests")

    def save(self, guest: Guest) -> None:
        self.store.write("guests", guest.handle, guest.model_dump(mode="json"))

    def get(self, handle: str) -> Guest | None:
        data = self.store.read("guests", handle)
        return Guest(**data) if data else None

    def list(self) -> list[Guest]:
        return [Guest(**g) for g in self.store.list("guests")]
