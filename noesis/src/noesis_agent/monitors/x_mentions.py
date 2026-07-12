from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from noesis_agent.clients.x_client import XClient
from noesis_agent.utils.noesislogger import NoesisLogger


MentionCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class XMentionsMonitor:
    """Polls X mentions, persists checkpoint state, and forwards mentions to a callback."""

    def __init__(
        self,
        x_client: XClient,
        store: Any | None = None,
        poll_seconds: int = 300,
        state_namespace: str = "runtime",
        state_key: str = "x_mentions_checkpoint",
    ) -> None:
        self.x_client = x_client
        self.store = store
        self.poll_seconds = max(15, int(poll_seconds))
        self.state_namespace = state_namespace
        self.state_key = state_key
        self.logger = NoesisLogger("noesis_agent.monitors.x_mentions").logger

        self._running = False
        self._stop_event = asyncio.Event()
        self._since_id: str | None = self._load_checkpoint()

    def _load_checkpoint(self) -> str | None:
        if self.store is None:
            return None

        try:
            payload = self.store.read(self.state_namespace, self.state_key)
        except Exception as exc:
            self.logger.warning("Failed to load X mention checkpoint", exc_info=exc)
            return None

        if not payload:
            return None

        value = str(payload.get("since_id", "")).strip()
        return value or None

    def _save_checkpoint(self, since_id: str) -> None:
        if self.store is None or not since_id:
            return

        try:
            self.store.write(
                self.state_namespace,
                self.state_key,
                {
                    "since_id": since_id,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as exc:
            self.logger.warning("Failed to persist X mention checkpoint", exc_info=exc)

    @staticmethod
    def _is_newer_tweet_id(candidate: str, current: str | None) -> bool:
        try:
            return current is None or int(candidate) > int(current)
        except (TypeError, ValueError):
            return bool(candidate) and candidate != current

    async def _invoke_callback(self, callback: MentionCallback, mention: dict[str, Any]) -> None:
        result = callback(mention)
        if inspect.isawaitable(result):
            await result

    async def run(self, callback: MentionCallback) -> None:
        if not self.x_client.is_enabled():
            self.logger.info("X client disabled; mentions monitor not started")
            return

        self._running = True
        self._stop_event.clear()

        try:
            try:
                me = self.x_client.get_authenticated_user()
                if me:
                    self.logger.info(
                        "X mentions monitor started",
                        extra={
                            "x_user_id": me.get("id"),
                            "since_id": self._since_id,
                            "poll_seconds": self.poll_seconds,
                        },
                    )
                else:
                    self.logger.warning("Authenticated X user unavailable; mentions monitor not started")
                    return
            except Exception as exc:
                self.logger.warning("Failed to validate authenticated X user", exc_info=exc)
                return

            while self._running and not self._stop_event.is_set():
                try:
                    mentions = self.x_client.get_mentions(
                        since_id=self._since_id,
                        max_results=10,
                    ) or []

                    mentions = sorted(
                        mentions,
                        key=lambda item: int(str(item.get("id", "0")) or "0"),
                    )

                    if mentions:
                        self.logger.info(
                            "X mentions fetched",
                            extra={
                                "count": len(mentions),
                                "since_id": self._since_id,
                            },
                        )

                    for mention in mentions:
                        mention_id = str(mention.get("id", "")).strip()
                        author_username = str(mention.get("author_username", "unknown")).strip() or "unknown"
                        text_preview = str(mention.get("text", "")).strip()[:160]

                        try:
                            await self._invoke_callback(callback, mention)
                        except Exception as exc:
                            self.logger.warning(
                                "Mention callback failed",
                                exc_info=exc,
                                extra={
                                    "tweet_id": mention_id or None,
                                    "author_username": author_username,
                                },
                            )
                            continue

                        if self._is_newer_tweet_id(mention_id, self._since_id):
                            self._since_id = mention_id
                            self._save_checkpoint(self._since_id)

                        self.logger.info(
                            "X mention processed",
                            extra={
                                "tweet_id": mention_id or None,
                                "author_username": author_username,
                                "message_preview": text_preview,
                            },
                        )

                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.logger.warning("Mention polling failed", exc_info=exc)

                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_seconds)
                except asyncio.TimeoutError:
                    continue
        finally:
            self._running = False
            self.logger.info("X mentions monitor stopped")

    async def run_normalized(self, callback: Callable[[Any], Awaitable[None] | None], *, handle: str) -> None:
        from noesis_agent.platforms.mention_normalizers import normalize_x_mention

        async def normalized_callback(payload: dict[str, Any]) -> None:
            result = callback(normalize_x_mention(payload, handle=handle))
            if inspect.isawaitable(result):
                await result

        await self.run(normalized_callback)

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
