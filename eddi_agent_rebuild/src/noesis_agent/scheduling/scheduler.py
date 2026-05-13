from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Callable

from noesis_agent.utils.noesislogger import NoesisLogger


class Scheduler:
    def __init__(self) -> None:
        self.logger = NoesisLogger("noesis.scheduling.scheduler").logger
        self.tasks: list[asyncio.Task] = []

    def schedule(self, when: datetime, callback: Callable, *args, **kwargs) -> asyncio.Task:
        delay = max(0.0, (when - datetime.utcnow()).total_seconds())

        async def _runner():
            await asyncio.sleep(delay)
            await callback(*args, **kwargs)

        task = asyncio.create_task(_runner())
        self.tasks.append(task)
        return task
