from __future__ import annotations

from noesis_agent.runtime.monitors.guest_watch import GuestWatch


class GuestJoinPipeline:
    def __init__(self, watcher: GuestWatch) -> None:
        self.watcher = watcher

    async def run(self, guest_handle: str) -> None:
        await self.watcher.on_join(guest_handle)
