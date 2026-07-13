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
            "owns this server", "server owner", "runs this guild", "created this server",
            "server made", "server created", "how old is this server", "who is in voice",
            "how many people are here", "how many people can see", "what permissions",
            "members does this channel", "channel visibility", "channel history", "what happened earlier",
        ))

    def inspect(self, event: MentionEvent, message: Any, *, authorized: bool) -> Evidence:
        if not authorized:
            return Evidence("discord", event.event_id, {}, {}, confidence=0.0, authorized=False,
                            tool_name=self.tool_id, limitation="authorization_required")
        guild = getattr(message, "guild", None)
        channel = getattr(message, "channel", None)
        author = getattr(message, "author", None)
        owner = getattr(guild, "owner", None)
        guild_id = getattr(guild, "id", None)
        created_at = getattr(guild, "created_at", None)
        if created_at is None and guild_id:
            from datetime import datetime, timezone
            created_at = datetime.fromtimestamp(((int(guild_id) >> 22) + 1420070400000) / 1000,
                                                 tz=timezone.utc)
        members = list(getattr(guild, "members", []) or [])
        member_count = getattr(guild, "member_count", None)
        cache_complete = bool(getattr(guild, "chunked", False)) or (
            member_count is not None and len(members) == member_count)
        visible_count = None
        permissions_for = getattr(channel, "permissions_for", None)
        if cache_complete and callable(permissions_for):
            try:
                visible_count = sum(bool(getattr(permissions_for(member), "view_channel", False))
                                    for member in members)
            except Exception:
                visible_count = None
        online_count = None
        if members and all(hasattr(member, "status") for member in members):
            online_count = sum(str(getattr(member, "status", "offline")).lower() != "offline"
                               for member in members)
        roles = [getattr(role, "name", None) for role in list(getattr(guild, "roles", []) or [])]
        author_roles = [getattr(role, "name", None) for role in list(getattr(author, "roles", []) or [])]
        bot_permissions = getattr(getattr(guild, "me", None), "guild_permissions", None)
        bot_permission_names = [name for name, enabled in bot_permissions] if bot_permissions is not None else None
        channel_created = getattr(channel, "created_at", None)
        parent = getattr(channel, "parent", None)
        facts = {
            "guild_name": getattr(guild, "name", None),
            "guild_id": str(guild_id) if guild_id is not None else None,
            "guild_owner_id": str(getattr(guild, "owner_id", None)) if getattr(guild, "owner_id", None) else None,
            "guild_owner_display_name": getattr(owner, "display_name", None) or getattr(owner, "name", None),
            "guild_created_at": created_at.isoformat() if created_at else None,
            "member_count": member_count,
            "cached_member_count": len(members),
            "member_cache_complete": cache_complete,
            "online_presence_count": online_count,
            "role_names": [name for name in roles if name],
            "bot_guild_permissions": bot_permission_names,
            "guild_features": list(getattr(guild, "features", []) or []),
            "guild_verification_level": str(getattr(guild, "verification_level", "")) or None,
            "channel_name": getattr(channel, "name", None),
            "channel_id": str(getattr(channel, "id", "")) or None,
            "channel_type": event.metadata.get("channel_type"),
            "channel_created_at": channel_created.isoformat() if channel_created else None,
            "parent_channel_name": getattr(parent, "name", None),
            "parent_channel_id": str(getattr(parent, "id", "")) or None,
            "channel_topic": getattr(channel, "topic", None),
            "channel_nsfw": getattr(channel, "nsfw", None),
            "channel_slowmode_seconds": getattr(channel, "slowmode_delay", None),
            "cached_visible_member_count": visible_count,
            "voice_participant_count": len(getattr(channel, "members", []) or []) if "voice" in str(event.metadata.get("channel_type", "")) else None,
            "is_thread": bool(event.metadata.get("is_thread")),
            "thread_owner_id": str(getattr(channel, "owner_id", None)) if getattr(channel, "owner_id", None) else None,
            "thread_participant_count": getattr(channel, "member_count", None) if event.metadata.get("is_thread") else None,
            "thread_auto_archive_minutes": getattr(channel, "auto_archive_duration", None) if event.metadata.get("is_thread") else None,
            "thread_archived": getattr(channel, "archived", None) if event.metadata.get("is_thread") else None,
            "thread_locked": getattr(channel, "locked", None) if event.metadata.get("is_thread") else None,
            "requesting_member_id": str(getattr(author, "id", "")) or None,
            "requesting_member_display_name": getattr(author, "display_name", None) or getattr(author, "name", None),
            "requesting_member_roles": [name for name in author_roles if name],
            "requesting_member_joined_at": getattr(getattr(author, "joined_at", None), "isoformat", lambda: None)(),
            "requesting_member_created_at": getattr(getattr(author, "created_at", None), "isoformat", lambda: None)(),
            "requesting_member_is_bot": getattr(author, "bot", None),
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
