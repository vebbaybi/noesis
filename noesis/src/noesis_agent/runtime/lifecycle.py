from __future__ import annotations

import asyncio
import signal
import sys
from contextlib import suppress
from typing import Any

from noesis_agent.interfaces.commands.handler import CommandHandler
from noesis_agent.infrastructure.config.settings import SettingsIssue, settings
from noesis_agent.runtime.shutdown import ShutdownManager
from noesis_agent.runtime.api_server import APIServer
from noesis_agent.runtime.background import BackgroundServiceManager
from noesis_agent.shared.errors import ConfigurationError
from noesis_agent.shared.noesislogger import NoesisLogger
from noesis_agent.shared.logging import sanitize_log_extra
from noesis_agent.runtime.identity import runtime_identity


class ApplicationLifecycle:
    """Coordinates settings validation, service startup, background tasks, and shutdown."""

    def __init__(self) -> None:
        self.logger = NoesisLogger(
            logger_name="noesis_agent.runtime.lifecycle",
            configure_on_init=True,
            level=getattr(settings, "log_level", "INFO"),
            env=getattr(settings, "env", "development"),
            service_name="noesis_agent",
            log_dir=getattr(settings, "log_dir", "logs"),
            enable_json=getattr(settings, "enable_json_logs", False),
            enable_alerts=getattr(settings, "enable_alerts", False),
            alert_webhook=getattr(settings, "alert_webhook", None),
        ).logger

        self.shutdown_manager = ShutdownManager()
        self.command_handler = CommandHandler()
        self.api_server = APIServer(self.shutdown_manager)
        self.background_manager = BackgroundServiceManager(self.shutdown_manager)
        self._shutdown_task: asyncio.Task[Any] | None = None

    def _validate_environment(self) -> None:
        issues = settings.validate_environment()
        for issue in issues:
            log_payload = sanitize_log_extra({
                "config_key": issue.key,
                "severity": issue.severity,
                "validation_message": issue.message,
            })
            if issue.severity == "error":
                self.logger.error("Configuration validation error", extra=log_payload)
            else:
                self.logger.warning("Configuration validation warning", extra=log_payload)

        errors = [issue for issue in issues if issue.severity == "error"]
        if errors:
            raise ConfigurationError(
                "NOESIS configuration is not valid for startup.",
                details={"issues": [self._issue_to_dict(issue) for issue in errors]},
            )

    @staticmethod
    def _issue_to_dict(issue: SettingsIssue) -> dict[str, str]:
        return {"key": issue.key, "severity": issue.severity, "message": issue.message}

    async def start(self) -> None:
        self._validate_environment()
        self._install_signal_handlers()

        identity = runtime_identity()
        identity["memory_hygiene_scan"] = self.background_manager.container.memory.diagnostics().get("last_hygiene_scan")
        self.logger.info("NOESIS runtime identity", extra=sanitize_log_extra(identity))

        self.logger.info(
            "NOESIS Agent booting up",
            extra={
                "environment": str(getattr(settings, "env", "development")),
                "host": str(getattr(settings, "host", "0.0.0.0")),
                "port": int(getattr(settings, "port", 8080)),
                "api_enabled": bool(getattr(settings, "enable_api", True)),
                "discord_enabled": bool(getattr(settings, "enable_discord", False)),
                "x_enabled": bool(getattr(settings, "enable_x", False)),
                "cognition_provider": str(getattr(settings, "cognition_provider", "auto")),
            },
        )

        if getattr(settings, "enable_api", True):
            await self.api_server.start()
        else:
            self.logger.info("FastAPI server disabled by configuration")

        await self.background_manager.start_all(self.command_handler)

    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()

        def _schedule_shutdown() -> None:
            if self.shutdown_manager.is_shutdown_requested():
                return
            if self._shutdown_task is None or self._shutdown_task.done():
                self._shutdown_task = asyncio.create_task(self.shutdown(), name="app-shutdown")

        if sys.platform != "win32":
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, _schedule_shutdown)
                except RuntimeError:
                    self.logger.warning("Signal handlers not supported in this environment")
                    break
        else:
            self.logger.info("Windows detected. Using KeyboardInterrupt/SystemExit for shutdown.")

    async def wait_for_shutdown(self) -> None:
        pending = set(self.background_manager.tasks())
        if not pending:
            await self.shutdown_manager.wait()
            return

        shutdown_waiter = asyncio.create_task(self.shutdown_manager.wait(), name="shutdown-waiter")
        try:
            while pending and not self.shutdown_manager.is_shutdown_requested():
                done, pending = await asyncio.wait(
                    pending | {shutdown_waiter},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if shutdown_waiter in done:
                    break
                refreshed = set(self.background_manager.tasks())
                pending |= {task for task in refreshed if not task.done()}
        finally:
            shutdown_waiter.cancel()
            with suppress(asyncio.CancelledError):
                await shutdown_waiter

    async def shutdown(self) -> None:
        if not self.shutdown_manager.is_shutdown_requested():
            self.logger.info("Shutdown signal received. Stopping services.")
            await self.shutdown_manager.request_shutdown()
        await self.shutdown_manager.run_handlers()
        self.logger.info("NOESIS shutdown complete")

    async def run(self) -> None:
        try:
            await self.start()
            await self.wait_for_shutdown()
        except asyncio.CancelledError:
            self.logger.info("Lifecycle task cancelled")
            raise
        finally:
            await self.shutdown()


__all__ = ["ApplicationLifecycle"]
