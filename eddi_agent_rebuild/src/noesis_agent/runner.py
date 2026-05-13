from __future__ import annotations

import asyncio

from noesis_agent.config.settings import settings
from noesis_agent.core.lifecycle import ApplicationLifecycle
from noesis_agent.utils.noesislogger import NoesisLogger


logger = NoesisLogger(
    logger_name="noesis_agent.runner",
    configure_on_init=True,
    level=getattr(settings, "log_level", "INFO"),
    env=getattr(settings, "env", "development"),
    service_name="noesis_agent",
    log_dir=getattr(settings, "log_dir", "logs"),
).logger


async def main() -> None:
    lifecycle = ApplicationLifecycle()
    await lifecycle.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("NOESIS stopped by user or system")
    except Exception as exc:
        logger.critical("Fatal startup failure", exc_info=exc)
        raise
