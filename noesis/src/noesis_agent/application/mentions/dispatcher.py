from __future__ import annotations

from typing import Any

from noesis_agent.application.ports import DisabledRuntimeOptions, RuntimeOptions
from noesis_agent.domain.contracts.mentions import MentionDispatchResult, MentionEvent


class MentionDispatcher:
    def __init__(self, mention_service, *, runtime_settings: RuntimeOptions | None = None,
                 discord_sender: Any = None, x_client: Any = None) -> None:
        self.mentions = mention_service
        self.settings = runtime_settings or DisabledRuntimeOptions()
        self.discord_sender = discord_sender
        self.x_client = x_client

    async def dispatch(self, event: MentionEvent, *, live: bool = False,
                       discord_sender: Any = None) -> MentionDispatchResult:
        response = await self.mentions.handle(event, dry_run=not live)
        base = dict(platform=event.platform, event_id=event.event_id, intent=response.intent,
                    response_status=response.status, response_text=response.text)
        if not response.should_respond:
            return MentionDispatchResult(**base, send_mode="disabled", disabled_reason=response.reason)
        if not live:
            return MentionDispatchResult(**base, send_mode="dry_run", send_result="No live send requested.")
        if event.platform == "discord":
            if not self.settings.enable_live_mention_send or not self.settings.enable_discord_mention_send:
                return MentionDispatchResult(**base, send_mode="disabled",
                    disabled_reason="Live Discord mention sending is disabled by configuration.")
            if not self.settings.enable_discord or not self.settings.discord_bot_token:
                missing = [] if self.settings.discord_bot_token else ["DISCORD_BOT_TOKEN"]
                return MentionDispatchResult(**base, send_mode="disabled",
                    disabled_reason="Discord live sending is disabled or not configured.", missing_credentials=missing)
            return await self._send_discord(base, response.text, discord_sender or self.discord_sender)
        if event.platform == "x":
            required = {"X_API_KEY": self.settings.x_api_key, "X_API_SECRET": self.settings.x_api_secret,
                        "X_ACCESS_TOKEN": self.settings.x_access_token,
                        "X_ACCESS_TOKEN_SECRET": self.settings.x_access_token_secret}
            missing = [key for key, value in required.items() if not value]
            if not self.settings.enable_x or missing:
                return MentionDispatchResult(**base, send_mode="disabled",
                    disabled_reason="X live sending is disabled or not configured.", missing_credentials=missing)
            return await self._send_x(base, response.text, event.event_id)
        return MentionDispatchResult(**base, send_mode="disabled",
                                     disabled_reason="This platform has no live mention sender.")

    async def _send_discord(self, base: dict[str, Any], text: str, sender: Any) -> MentionDispatchResult:
        if sender is None:
            return MentionDispatchResult(**base, send_mode="failed", send_attempted=False,
                                         send_result="No connected Discord message sender is available.",
                                         error_category="sender_unavailable")
        try:
            result = sender(text[:2000])
            if hasattr(result, "__await__"):
                result = await result
            return MentionDispatchResult(**base, send_mode="succeeded", send_attempted=True,
                                         send_result="Discord reply sent.",
                                         sent_message_id=str(getattr(result, "id", "")) or None)
        except Exception:
            return MentionDispatchResult(**base, send_mode="failed", send_attempted=True,
                                         send_result="Discord reply failed; see sanitized application logs.",
                                         error_category="platform_send_error")

    async def _send_x(self, base: dict[str, Any], text: str, reply_id: str) -> MentionDispatchResult:
        if self.x_client is None:
            return MentionDispatchResult(**base, send_mode="failed", send_attempted=False,
                                         send_result="No configured X client is available.")
        result = self.x_client.post(text[:280], reply_to_tweet_id=reply_id, dry_run=False)
        status = str(result.get("status", "error"))
        if status == "success":
            return MentionDispatchResult(**base, send_mode="succeeded", send_attempted=True,
                                         send_result=f"X reply sent ({result.get('tweet_id', 'no receipt id')}).")
        return MentionDispatchResult(**base, send_mode="failed", send_attempted=True,
                                     send_result="X reply failed; see sanitized application logs.")


__all__ = ["MentionDispatcher"]
