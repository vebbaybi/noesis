from __future__ import annotations

from typing import Any

from noesis_agent.cognition.evidence import Evidence
from noesis_agent.models.mentions import MentionEvent


class DiscordContextTool:
    tool_id = "discord.current_context"

    @staticmethod
    def is_needed(text: str) -> bool:
        lower = text.lower()
        return any(marker in lower for marker in (
            "member count", "how many members", "which channel", "what channel",
            "what server", "which server", "this thread", "gateway latency",
        ))

    def inspect(self, event: MentionEvent, message: Any, *, authorized: bool) -> Evidence:
        if not authorized:
            return Evidence("discord", event.event_id, {}, {}, confidence=0.0, authorized=False,
                            tool_name=self.tool_id, limitation="authorization_required")
        guild = getattr(message, "guild", None)
        channel = getattr(message, "channel", None)
        facts = {
            "guild_name": getattr(guild, "name", None),
            "member_count": getattr(guild, "member_count", None),
            "channel_name": getattr(channel, "name", None),
            "channel_type": event.metadata.get("channel_type"),
            "is_thread": bool(event.metadata.get("is_thread")),
            "thread_archived": getattr(channel, "archived", None) if event.metadata.get("is_thread") else None,
            "thread_locked": getattr(channel, "locked", None) if event.metadata.get("is_thread") else None,
        }
        facts = {key: value for key, value in facts.items() if value is not None}
        return Evidence(
            source_type="discord_gateway_object", source_id=event.event_id,
            scope={"guild_id": event.metadata.get("guild_id"),
                   "channel_id": event.channel_id,
                   "conversation_id": event.conversation_id},
            facts=facts, tool_name=self.tool_id,
            limitation="Only metadata present on the authorized current gateway event is included.",
        )


__all__ = ["DiscordContextTool"]
