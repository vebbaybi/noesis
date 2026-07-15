from __future__ import annotations

import asyncio
import inspect
import signal
import sys
from typing import Awaitable, Callable

from noesis_agent.shared.noesislogger import NoesisLogger

ShutdownHandler = Callable[[], Awaitable[None] | None]


class ShutdownManager:
    """Manages graceful shutdown of all services."""

    def __init__(self) -> None:
        self.logger = NoesisLogger(
            logger_name="noesis_agent.runtime.shutdown",
        ).logger

        self._event = asyncio.Event()
        self._handlers: list[ShutdownHandler] = []
        self._lock = asyncio.Lock()
        self._handlers_executed = False

    def register_shutdown_handler(self, handler: ShutdownHandler) -> None:
        """Register a shutdown handler."""
        self._handlers.append(handler)

    def setup_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        """Setup signal handlers for graceful shutdown."""
        if sys.platform == "win32":
            self.logger.info("Windows detected, signal handlers not supported")
            return

        def _signal_handler() -> None:
            if not self.is_shutdown_requested():
                asyncio.create_task(self.trigger_shutdown())

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _signal_handler)
            except RuntimeError:
                self.logger.warning(f"Signal handler for {sig} not supported")
                break

    async def trigger_shutdown(self) -> None:
        """Trigger graceful shutdown."""
        await self.request_shutdown()
        await self.execute_handlers()

    async def request_shutdown(self) -> None:
        async with self._lock:
            if self._event.is_set():
                return
            self.logger.info("Shutdown triggered")
            self._event.set()

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._event.wait()

    async def wait(self) -> None:
        await self.wait_for_shutdown()

    async def execute_handlers(self) -> None:
        """Execute all registered shutdown handlers."""
        async with self._lock:
            if self._handlers_executed:
                return
            self._handlers_executed = True

        if not self._handlers:
            return

        self.logger.info(f"Executing {len(self._handlers)} shutdown handlers")

        for handler in reversed(self._handlers):
            try:
                result = handler()
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                self.logger.error("Shutdown handler failed", exc_info=exc)

    async def run_handlers(self) -> None:
        await self.execute_handlers()

    def is_shutdown_requested(self) -> bool:
        return self._event.is_set()

    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self.is_shutdown_requested()
