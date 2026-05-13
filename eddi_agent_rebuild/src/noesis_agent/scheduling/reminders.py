from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Callable


class ReminderService:
    def __init__(self) -> None:
        self._tasks: list[asyncio.Task] = []

    def schedule_reminder(self, when: datetime, message: str, callback: Callable[[str], None]) -> None:
        delay = max(0.0, (when - datetime.utcnow()).total_seconds())

        async def _run():
            await asyncio.sleep(delay)
            await callback(message)

        self._tasks.append(asyncio.create_task(_run()))
