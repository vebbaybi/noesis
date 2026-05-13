from __future__ import annotations

from noesis_agent.clients.openai_client import OpenAIService


class AbuseDetector:
    """Detects abusive or toxic input using simple keyword checks plus OpenAI moderation if available."""

    def __init__(self, openai: OpenAIService | None = None) -> None:
        self.openai = openai
        self.blocklist = {"hate", "racist", "slur", "bomb", "kill", "suicide"}

    async def is_abusive(self, text: str) -> bool:
        lower = text.lower()
        if any(word in lower for word in self.blocklist):
            return True
        if self.openai and self.openai.is_enabled():
            try:
                response = await self.openai.client.moderations.create(
                    model="omni-moderation-latest",
                    input=text,
                )
                result = response.results[0]
                return bool(result.flagged)
            except Exception:
                return False
        return False
