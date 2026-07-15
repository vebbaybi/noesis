from __future__ import annotations


class MutePolicy:
    def should_mute(self, speaker: str, strike_count: int) -> bool:
        return strike_count >= 2
