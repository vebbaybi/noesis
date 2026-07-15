from __future__ import annotations

from noesis_agent.capabilities.moderation.room_moderator import RoomModerator, ModerationDecision
from noesis_agent.capabilities.moderation.abuse_detector import AbuseDetector
from noesis_agent.capabilities.moderation.spam_detector import SpamDetector


class ModerationService:
    def __init__(self, moderator: RoomModerator | None = None) -> None:
        self.moderator = moderator or RoomModerator(AbuseDetector(), SpamDetector())

    async def evaluate(self, speaker: str, text: str) -> ModerationDecision:
        return await self.moderator.evaluate(speaker, text)
