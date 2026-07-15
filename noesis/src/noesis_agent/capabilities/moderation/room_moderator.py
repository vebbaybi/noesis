from __future__ import annotations

from dataclasses import dataclass, field

from noesis_agent.capabilities.moderation.abuse_detector import AbuseDetector
from noesis_agent.capabilities.moderation.spam_detector import SpamDetector
from noesis_agent.capabilities.moderation.speaker_queue import SpeakerQueue
from noesis_agent.capabilities.moderation.mute_policy import MutePolicy
from noesis_agent.capabilities.moderation.interruption_policy import InterruptionPolicy


@dataclass
class ModerationDecision:
    action: str  # allow | mute | warn | drop
    reason: str
    speaker: str | None = None


class RoomModerator:
    def __init__(self, abuse: AbuseDetector, spam: SpamDetector) -> None:
        self.abuse = abuse
        self.spam = spam
        self.queue = SpeakerQueue()
        self.mute_policy = MutePolicy()
        self.interrupt_policy = InterruptionPolicy()
        self.strikes: dict[str, int] = {}

    async def evaluate(self, speaker: str, text: str) -> ModerationDecision:
        if await self.abuse.is_abusive(text):
            self._strike(speaker)
            return ModerationDecision("mute", "abusive content", speaker)

        if self.spam.is_spam(speaker, text):
            self._strike(speaker)
            if self.strikes[speaker] > 1:
                return ModerationDecision("mute", "spam", speaker)
            return ModerationDecision("warn", "spam", speaker)

        return ModerationDecision("allow", "clean")

    def _strike(self, speaker: str) -> None:
        self.strikes[speaker] = self.strikes.get(speaker, 0) + 1

    def should_interrupt(self, speaking_seconds: float) -> bool:
        return self.interrupt_policy.should_interrupt(speaking_seconds, len(self.queue.list()))
