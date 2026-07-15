from __future__ import annotations

import asyncio
import threading

import uvicorn

from noesis_agent.interfaces.api.app import app
from noesis_agent.infrastructure.config.settings import settings
from noesis_agent.shared.noesislogger import NoesisLogger


class APIServer:
    """Runs the FastAPI app inside a background thread with clean shutdown."""

    def __init__(self, shutdown_manager) -> None:
        self.logger = NoesisLogger("noesis.api.server").logger
        self.shutdown_manager = shutdown_manager
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._startup_event = threading.Event()
        self._failed_event = threading.Event()
        self._exception: Exception | None = None

    def _run(self) -> None:
        try:
            config = uvicorn.Config(
                app=app,
                host=str(getattr(settings, "host", "0.0.0.0")),
                port=int(getattr(settings, "port", 8080)),
                log_level=str(getattr(settings, "log_level", "info")).lower(),
                access_log=True,
            )
            self._server = uvicorn.Server(config)
            self._startup_event.set()
            self._server.run()
        except Exception as exc:  # pragma: no cover - startup failures
            self._exception = exc
            self._failed_event.set()
            self._startup_event.set()

    async def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._startup_event.clear()
        self._failed_event.clear()
        self._exception = None
        self._thread = threading.Thread(target=self._run, daemon=True, name="uvicorn-thread")
        self._thread.start()

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._startup_event.wait)

        if self._failed_event.is_set():
            if self._exception:
                raise self._exception
            raise RuntimeError("API server failed to start")

        self.logger.info(
            "FastAPI server started",
            extra={
                "host": settings.host,
                "port": settings.port,
                "operator_url": self.operator_url(),
            },
        )

        self.shutdown_manager.register_shutdown_handler(self.stop)

    @staticmethod
    def operator_url() -> str:
        host = str(settings.host)
        browser_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
        return f"http://{browser_host}:{settings.port}/operator"

    async def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
            self.logger.info("API server shutdown requested")

        if self._thread and self._thread.is_alive():
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._thread.join, 10.0)
            if self._thread.is_alive():
                self.logger.warning("API server thread did not exit cleanly")

        self._thread = None
        self._server = None
