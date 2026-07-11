from __future__ import annotations

import asyncio
from noesis_agent.utils.noesislogger import NoesisLogger


class LiveSessionMonitor:
    """Checks liveness of active sessions and triggers alerts if idle."""

    def __init__(self, idle_seconds: int = 120) -> None:
        self.idle_seconds = idle_seconds
        self.logger = NoesisLogger("noesis.monitors.live_session").logger
        self._running = False
        self._last_activity = asyncio.get_event_loop().time()

    def mark_activity(self) -> None:
        self._last_activity = asyncio.get_event_loop().time()

    async def run(self, alert_callback) -> None:
        self._running = True
        while self._running:
            await asyncio.sleep(self.idle_seconds)
            if asyncio.get_event_loop().time() - self._last_activity > self.idle_seconds:
                await alert_callback("Session idle for too long")

    def stop(self) -> None:
        self._running = False
