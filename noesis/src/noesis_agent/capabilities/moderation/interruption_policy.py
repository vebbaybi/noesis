from __future__ import annotations


class InterruptionPolicy:
    """Decides whether the bot should cut in based on duration and queue."""

    def should_interrupt(self, speaking_seconds: float, queue_length: int) -> bool:
        if speaking_seconds > 90 and queue_length > 0:
            return True
        if speaking_seconds > 150:
            return True
        return False
