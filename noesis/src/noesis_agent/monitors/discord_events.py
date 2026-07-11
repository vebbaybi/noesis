from __future__ import annotations

import asyncio
import inspect
from typing import Any, Awaitable, Callable

from noesis_agent.utils.noesislogger import NoesisLogger


class DiscordEventsMonitor:
    """Queue-backed Discord event monitor for tests and injected gateway callbacks."""

    def __init__(self) -> None:
        self.logger = NoesisLogger("noesis.monitors.discord").logger
        self._running = False
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def publish_event(self, event: dict[str, Any]) -> None:
        payload = dict(event)
        payload.setdefault("source", "discord")
        await self._queue.put(payload)

    async def run(self, callback: Callable[[dict[str, Any]], Awaitable[None] | None]) -> None:
        self._running = True
        while self._running:
            event = await self._queue.get()
            try:
                result = callback(event)
                if inspect.isawaitable(result):
                    await result
            finally:
                self._queue.task_done()

    def stop(self) -> None:
        self._running = False
        self._queue.put_nowait({"source": "discord", "event_type": "monitor_stopped"})
