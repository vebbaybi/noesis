from __future__ import annotations

from datetime import datetime, timedelta


class CalendarSync:
    """Local calendar availability helper used before external calendar connectors exist."""

    def __init__(self, busy_windows: list[tuple[datetime, datetime]] | None = None) -> None:
        self.busy_windows = sorted(busy_windows or [], key=lambda window: window[0])

    def find_slot(self, start: datetime, duration_minutes: int = 60) -> datetime:
        if duration_minutes <= 0:
            raise ValueError("duration_minutes must be greater than zero")

        candidate = start
        duration = timedelta(minutes=duration_minutes)

        for busy_start, busy_end in self.busy_windows:
            if busy_end <= candidate:
                continue
            if candidate + duration <= busy_start:
                return candidate
            candidate = max(candidate, busy_end)

        return candidate
