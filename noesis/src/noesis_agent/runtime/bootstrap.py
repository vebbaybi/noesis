"""Canonical process bootstrap for Noesis."""

from __future__ import annotations

import asyncio

from noesis_agent.infrastructure.config.settings import settings
from noesis_agent.runtime.lifecycle import ApplicationLifecycle
from noesis_agent.shared.noesislogger import NoesisLogger


logger = NoesisLogger(
    logger_name="noesis_agent.runtime.bootstrap",
    configure_on_init=True,
    level=getattr(settings, "log_level", "INFO"),
    env=getattr(settings, "env", "development"),
    service_name="noesis_agent",
    log_dir=getattr(settings, "log_dir", "logs"),
).logger


async def main() -> None:
    await ApplicationLifecycle().run()


def run() -> None:
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("NOESIS stopped by user or system")
    except Exception as exc:
        logger.critical("Fatal startup failure", exc_info=exc)
        raise
