from __future__ import annotations

from noesis_agent.shared.noesislogger import NoesisLogger


class GuestWatch:
    def __init__(self) -> None:
        self.logger = NoesisLogger("noesis.monitors.guest").logger

    async def on_join(self, guest_handle: str) -> None:
        self.logger.info("Guest joined", extra={"guest": guest_handle})

    async def on_leave(self, guest_handle: str) -> None:
        self.logger.info("Guest left", extra={"guest": guest_handle})
