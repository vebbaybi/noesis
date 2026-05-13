from __future__ import annotations

from noesis_agent.models.guest import Guest
from noesis_agent.store.guest_store import GuestStore


class GuestMemory:
    def __init__(self, store: GuestStore) -> None:
        self.store = store

    def remember(self, guest: Guest) -> None:
        self.store.save(guest)

    def recall(self, handle: str) -> Guest | None:
        return self.store.get(handle)
