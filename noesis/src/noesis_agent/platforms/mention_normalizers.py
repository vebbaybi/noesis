from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from noesis_agent.models.mentions import MentionEvent
from noesis_agent.platforms.discord_authorization import (
    DiscordAuthorizationDecision,
    extract_discord_channel_context,
)


def _get(value: Any, name: str, default: Any = None) -> Any:
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _id(value: Any) -> str | None:
    raw = _get(value, "id") if value is not None else None
    return str(raw) if raw is not None and str(raw) else None


def normalize_discord_message(message: Any, *, bot_user_id: str | int | None = None,
                              bot_name: str = "Noesis",
                              authorization: DiscordAuthorizationDecision | None = None,
                              thread_type: type[Any] | None = None) -> MentionEvent:
    author = _get(message, "author")
    channel = _get(message, "channel")
    reference = _get(message, "reference")
    parent = _get(reference, "resolved") or _get(message, "referenced_message")
    mentions = list(_get(message, "mentions", []) or [])
    bot_id = str(bot_user_id) if bot_user_id is not None else None
    mentioned = any(_id(item) == bot_id for item in mentions) if bot_id else bool(
        re.search(rf"(?i)(?:@|\b){re.escape(bot_name)}\b", str(_get(message, "content", "")))
    )
    parent_author = _get(parent, "author")
    reply_to_noesis = bool(parent and (
        (bot_id is not None and _id(parent_author) == bot_id)
        or bool(_get(parent_author, "bot", False) and
                str(_get(parent_author, "name", "")).lower() == bot_name.lower())
    ))
    attachments = []
    for item in list(_get(message, "attachments", []) or []):
        attachments.append({key: value for key, value in {
            "id": _id(item), "filename": _get(item, "filename"), "url": _get(item, "url"),
            "content_type": _get(item, "content_type"), "size": _get(item, "size"),
        }.items() if value is not None})
    timestamp = _get(message, "created_at") or datetime.now(timezone.utc)
    context = authorization.context if authorization is not None else extract_discord_channel_context(
        message, **({"thread_type": thread_type} if thread_type is not None else {})
    )
    return MentionEvent(
        event_id=_id(message) or "discord-unknown", platform="discord",
        user_id=_id(author), username=_get(author, "display_name") or _get(author, "name"),
        channel_id=context.current_channel_id,
        conversation_id=context.thread_id or context.current_channel_id,
        text=_get(message, "content", ""), parent_text=_get(parent, "content"),
        attachments=attachments, timestamp=timestamp, mentioned=mentioned,
        is_reply_to_noesis=reply_to_noesis,
        metadata={
            "message_id": _id(message),
            "current_channel_id": context.current_channel_id,
            "thread_id": context.thread_id,
            "parent_channel_id": context.parent_channel_id,
            "guild_id": context.guild_id,
            "is_thread": context.is_thread,
            "authorization_source": authorization.authorization_source if authorization else None,
            "authorization_reason": authorization.reason if authorization else None,
            "response_target_id": context.response_target_id,
            "channel_type": context.channel_type,
        },
    )


def normalize_x_mention(payload: Any, *, handle: str = "Noesis") -> MentionEvent:
    text = str(_get(payload, "text", "") or "")
    raw_attachments = _get(payload, "attachments", []) or _get(payload, "media", []) or []
    if isinstance(raw_attachments, dict):
        raw_attachments = raw_attachments.get("media_keys", [])
    attachments = [item if isinstance(item, dict) else {"id": str(item)} for item in raw_attachments]
    parent_text = _get(payload, "parent_text") or _get(_get(payload, "referenced_tweet"), "text")
    return MentionEvent(
        event_id=str(_get(payload, "id", "x-unknown")), platform="x", text=text,
        user_id=str(_get(payload, "author_id")) if _get(payload, "author_id") is not None else None,
        username=_get(payload, "author_username"),
        conversation_id=str(_get(payload, "conversation_id")) if _get(payload, "conversation_id") is not None else None,
        parent_text=parent_text, attachments=attachments,
        timestamp=_get(payload, "created_at") or datetime.now(timezone.utc),
        mentioned=bool(re.search(rf"(?i)@{re.escape(handle.lstrip('@'))}\b", text)),
        is_reply_to_noesis=bool(_get(payload, "is_reply_to_noesis", False)),
        metadata={"reply_to_tweet_id": _get(payload, "in_reply_to_tweet_id")},
    )


__all__ = ["normalize_discord_message", "normalize_x_mention"]
