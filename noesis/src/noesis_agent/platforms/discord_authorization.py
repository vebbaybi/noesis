from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Collection, Type

import discord


@dataclass(frozen=True, slots=True)
class DiscordChannelContext:
    current_channel_id: str | None
    thread_id: str | None
    parent_channel_id: str | None
    guild_id: str | None
    is_thread: bool
    channel_type: str
    response_target_id: str | None


@dataclass(frozen=True, slots=True)
class DiscordAuthorizationDecision:
    allowed: bool
    reason: str
    authorization_source: str | None
    context: DiscordChannelContext


def _snowflake(value: Any) -> str | None:
    if value is None:
        return None
    raw = getattr(value, "id", value)
    return str(raw) if raw is not None and str(raw) else None


def extract_discord_channel_context(
    message: Any,
    *,
    thread_type: Type[Any] = discord.Thread,
) -> DiscordChannelContext:
    channel = getattr(message, "channel", None)
    guild = getattr(message, "guild", None)
    current_id = _snowflake(channel)
    is_thread = isinstance(channel, thread_type)
    parent_id = None
    if is_thread:
        parent_id = _snowflake(getattr(channel, "parent_id", None))
        if parent_id is None:
            parent_id = _snowflake(getattr(channel, "parent", None))
    return DiscordChannelContext(
        current_channel_id=current_id,
        thread_id=current_id if is_thread else None,
        parent_channel_id=parent_id,
        guild_id=_snowflake(guild),
        is_thread=is_thread,
        channel_type=type(channel).__name__ if channel is not None else "missing",
        response_target_id=current_id,
    )


def authorize_discord_message(
    message: Any,
    allowed_channel_ids: Collection[int | str],
    *,
    thread_type: Type[Any] = discord.Thread,
) -> DiscordAuthorizationDecision:
    context = extract_discord_channel_context(message, thread_type=thread_type)
    allowed = {str(item) for item in allowed_channel_ids}
    if context.guild_id is None:
        return DiscordAuthorizationDecision(False, "guild_context_missing", None, context)
    if context.current_channel_id is None:
        return DiscordAuthorizationDecision(False, "channel_id_missing", None, context)
    if context.current_channel_id in allowed:
        return DiscordAuthorizationDecision(True, "authorized", "direct_channel", context)
    if context.is_thread:
        if context.parent_channel_id is None:
            return DiscordAuthorizationDecision(False, "thread_parent_unresolved", None, context)
        if context.parent_channel_id in allowed:
            return DiscordAuthorizationDecision(True, "authorized", "thread_parent", context)
        return DiscordAuthorizationDecision(False, "thread_parent_not_allowlisted", None, context)
    return DiscordAuthorizationDecision(False, "channel_not_allowlisted", None, context)


__all__ = [
    "DiscordAuthorizationDecision",
    "DiscordChannelContext",
    "authorize_discord_message",
    "extract_discord_channel_context",
]
