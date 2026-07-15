from __future__ import annotations

import re
from collections import OrderedDict, deque
from datetime import datetime, timezone
from typing import Any


class DiscordRecentContextBuffer:
    """Bounded, scoped, redacted context captured only after Discord authorization."""

    _SECRET = re.compile(
        r"(?i)(api[_ -]?key|token|password|secret|authorization)(\s*[:=]\s*)(\S+)|"
        r"\b(?:sk-|ghp_|xox[baprs]-)[A-Za-z0-9_-]{8,}"
    )
    _PROFANITY = re.compile(r"(?i)\b(fuck(?:ing|ed|er|s)?|cunt|shit(?:ty)?|bitch(?:es)?)\b")

    def __init__(self, *, per_scope_limit: int = 12, scope_limit: int = 128,
                 preview_char_limit: int = 1000) -> None:
        self.per_scope_limit = max(2, min(per_scope_limit, 50))
        self.scope_limit = max(4, min(scope_limit, 1000))
        self.preview_char_limit = max(100, min(preview_char_limit, 4000))
        self._scopes: OrderedDict[tuple[str, str, str], deque[dict[str, Any]]] = OrderedDict()

    @staticmethod
    def scope_key(event) -> tuple[str, str, str]:
        return (str(event.metadata.get("guild_id") or "direct"),
                str(event.channel_id or "direct"),
                str(event.metadata.get("thread_id") or event.conversation_id or "channel"))

    def capture(self, event, *, moderation: dict | None = None) -> None:
        key = self.scope_key(event)
        bucket = self._scopes.setdefault(key, deque(maxlen=self.per_scope_limit))
        bucket.append({
            "event_id": event.event_id, "platform": "discord",
            "guild_id": event.metadata.get("guild_id"), "channel_id": event.channel_id,
            "thread_id": event.metadata.get("thread_id"),
            "parent_channel_id": event.metadata.get("parent_channel_id"),
            "author_id": event.user_id, "author": event.username or "member",
            "timestamp": event.timestamp.isoformat() if event.timestamp else datetime.now(timezone.utc).isoformat(),
            "text": self._safe_preview(event.text),
            "moderation": self._safe_moderation(moderation),
        })
        self._scopes.move_to_end(key)
        while len(self._scopes) > self.scope_limit:
            self._scopes.popitem(last=False)

    def snapshot(self, event) -> list[dict[str, Any]]:
        return [dict(item) for item in self._scopes.get(self.scope_key(event), ())]

    def health(self) -> dict[str, int]:
        return {"scope_count": len(self._scopes),
                "entry_count": sum(len(bucket) for bucket in self._scopes.values()),
                "per_scope_limit": self.per_scope_limit, "scope_limit": self.scope_limit}

    def _safe_preview(self, text: str) -> str:
        value = " ".join(str(text or "").split())[:self.preview_char_limit]
        value = self._SECRET.sub(lambda match: f"{match.group(1) or 'credential'}{match.group(2) or ' '}[REDACTED]", value)
        return self._PROFANITY.sub("[profanity]", value)

    @staticmethod
    def _safe_moderation(signal: dict | None) -> dict | None:
        if not signal:
            return None
        return {key: signal.get(key) for key in
                ("category", "severity", "confidence", "target_status", "outcome", "safe_summary")}


__all__ = ["DiscordRecentContextBuffer"]
