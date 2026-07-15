from __future__ import annotations

import asyncio
import inspect
from dataclasses import asdict
from contextlib import suppress
from typing import Any

from noesis_agent.integrations.discord.client import NoesisDiscordBot
from noesis_agent.infrastructure.config.settings import settings
from noesis_agent.runtime.monitors.x_mentions import XMentionsMonitor
from noesis_agent.runtime.container import get_container
from noesis_agent.shared.noesislogger import NoesisLogger
from noesis_agent.integrations.discord.recent_context import DiscordRecentContextBuffer
from noesis_agent.runtime.identity import COGNITION_BUILD_ID


class BackgroundServiceManager:
    def __init__(self, shutdown_manager, container: Any | None = None) -> None:
        self.logger = NoesisLogger("noesis_agent.runtime.background").logger
        self.shutdown_manager = shutdown_manager
        self.container = container or get_container()

        self._tasks: list[asyncio.Task[Any]] = []
        self._discord_bot: NoesisDiscordBot | None = None
        self._x_monitor: XMentionsMonitor | None = None
        self._live_agent = None
        self._discord_recent = DiscordRecentContextBuffer()
        self._discord_last_response: dict[str, str] = {}

        self.shutdown_manager.register_shutdown_handler(self.stop_all)

    async def start_all(self, command_handler) -> None:
        self.logger.info("Starting background services")

        await self._start_discord_bot(command_handler)
        await self._start_live_agent()
        await self._start_x_monitor(command_handler)

        self.logger.info(
            "Background services started",
            extra={"count": len(self._tasks)},
        )

    async def _start_discord_bot(self, command_handler) -> None:
        if not getattr(settings, "enable_discord", False) or not getattr(settings, "discord_bot_token", None):
            self.logger.info("Discord bot disabled or missing token")
            return

        self._discord_bot = NoesisDiscordBot(
            command_handler.handle,
            live_agent_getter=lambda: getattr(self.container, "live", None),
            mention_callback=self._handle_discord_mention,
        )
        if hasattr(self.container, "bind_discord_client"):
            self.container.bind_discord_client(self._discord_bot)
        task = asyncio.create_task(
            self._discord_bot.start_with_config(),
            name="discord-bot",
        )
        self._track_task(task)
        self.logger.info("Discord bot task launched")

    async def _handle_discord_mention(self, event, message) -> None:
        dispatcher = getattr(self.container, "mention_dispatcher", None)
        if dispatcher is None:
            self.logger.error("Discord mention dispatcher unavailable", extra={"event_id": event.event_id})
            return

        context_key = "|".join(self._discord_recent.scope_key(event))
        event.metadata["recent_context"] = self._discord_recent.snapshot(event)
        if context_key in self._discord_last_response:
            event.metadata["previous_noesis_response"] = self._discord_last_response[context_key]

        async def reply_sender(text: str):
            return await message.reply(text, mention_author=False)

        context_tool = getattr(self.container, "discord_context_tool", None)
        # Gateway metadata is bounded, already authorized, and inexpensive.  Inspect
        # every addressed event so NLUâ€”not a phrase allowlistâ€”decides which fact is useful.
        if context_tool is not None:
            evidence = context_tool.inspect(event, message, authorized=True)
            event.metadata["evidence"] = [evidence.safe_dict()]

        live = bool(
            getattr(settings, "enable_live_mention_send", False)
            and getattr(settings, "enable_discord_mention_send", False)
        )
        moderation_classifier = getattr(getattr(self.container, "mentions", None), "moderation_classifier", None)
        moderation = moderation_classifier.classify(event.text) if moderation_classifier is not None else None
        self._discord_recent.capture(event, moderation=asdict(moderation) if moderation is not None else None)
        event.metadata["recent_context_buffer"] = self._discord_recent.health()
        result = await dispatcher.dispatch(event, live=live, discord_sender=reply_sender)
        if result.response_text:
            self._discord_last_response[context_key] = result.response_text[:2000]
        self.logger.info(
            "Discord mention processed",
            extra={
                "event_id": event.event_id,
                "response_status": result.response_status,
                "send_mode": result.send_mode,
                "send_attempted": result.send_attempted,
                "sent_message_id": result.sent_message_id,
                "error_category": result.error_category,
                "cognition_build_id": COGNITION_BUILD_ID,
            },
        )

    async def _start_live_agent(self) -> None:
        if not getattr(settings, "enable_live_agent", True):
            self.logger.info("Live media agent disabled")
            return

        if not getattr(settings, "auto_start_live_session", False):
            self.logger.info("Live media agent ready for on-demand Discord voice sessions")
            return

        self._live_agent = getattr(self.container, "live", None)
        if self._live_agent is None or not hasattr(self._live_agent, "start_autonomous_session"):
            self.logger.info("Live media agent unavailable")
            return

        if self._discord_bot is not None and hasattr(self._live_agent, "set_discord_client"):
            self._live_agent.set_discord_client(self._discord_bot)

        topic = str(getattr(settings, "auto_start_live_topic", "Open conversation") or "Open conversation")
        task = asyncio.create_task(self._live_agent.start_autonomous_session(topic=topic), name="live-media-agent")
        self._track_task(task)
        self.logger.info("Live media agent auto-start launched", extra={"topic": topic})

    async def _start_x_monitor(self, command_handler) -> None:
        x_client = getattr(self.container, "x_client", None)
        if not getattr(settings, "enable_x", False) or x_client is None or not x_client.is_enabled():
            self.logger.info("X mention monitoring disabled")
            return

        poll_seconds = int(getattr(settings, "x_mentions_poll_seconds", 300))
        store = getattr(self.container, "store", None)

        self._x_monitor = XMentionsMonitor(
            x_client=x_client,
            store=store,
            poll_seconds=poll_seconds,
        )

        task = asyncio.create_task(
            self._x_monitor.run(lambda mention: self._handle_x_mention(mention, command_handler)),
            name="x-mention-monitor",
        )
        self._track_task(task)
        self.logger.info("X mention monitor launched")

    async def _handle_x_mention(self, mention: dict[str, Any], command_handler) -> None:
        author_username = str(mention.get("author_username", "unknown")).strip() or "unknown"
        tweet_id = str(mention.get("id", "")).strip() or None
        text = str(mention.get("text", "")).strip()

        self.logger.info(
            "New X mention received",
            extra={
                "tweet_id": tweet_id,
                "author_username": author_username,
                "message_preview": text[:160],
            },
        )

        social_service = getattr(self.container, "social_service", None)
        if social_service is None:
            social_service = getattr(self.container, "social", None)

        if social_service is not None and hasattr(social_service, "handle_mention"):
            result = social_service.handle_mention(mention)
            if inspect.isawaitable(result):
                await result
            return

        if hasattr(command_handler, "handle"):
            result = command_handler.handle(
                "nft_insight",
                {"query": text or "trending NFTs"},
            )
            if inspect.isawaitable(result):
                await result

    def _track_task(self, task: asyncio.Task[Any]) -> None:
        self._tasks.append(task)
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task[Any]) -> None:
        with suppress(ValueError):
            self._tasks.remove(task)

        if task.cancelled():
            self.logger.info(
                "Background task cancelled",
                extra={"task_name": task.get_name()},
            )
            return

        exc = task.exception()
        if exc is not None:
            self.logger.error(
                "Background task failed",
                exc_info=exc,
                extra={"task_name": task.get_name()},
            )
        else:
            self.logger.info(
                "Background task completed",
                extra={"task_name": task.get_name()},
            )

    async def stop_all(self) -> None:
        if self._x_monitor is not None:
            self._x_monitor.stop()

        live_agent = self._live_agent or getattr(self.container, "_live", None)
        if live_agent is not None and hasattr(live_agent, "shutdown"):
            try:
                await live_agent.shutdown()
                self.logger.info("Live media agent closed")
            except Exception as exc:
                self.logger.error("Failed to close live media agent cleanly", exc_info=exc)

        if self._discord_bot is not None and not self._discord_bot.is_closed():
            try:
                await self._discord_bot.close()
                self.logger.info("Discord bot closed")
            except Exception as exc:
                self.logger.error("Failed to close Discord bot cleanly", exc_info=exc)

        if self._tasks:
            self.logger.info(
                "Stopping background services",
                extra={"count": len(self._tasks)},
            )

        current = asyncio.current_task()
        to_cancel = [task for task in list(self._tasks) if task is not current and not task.done()]

        for task in to_cancel:
            task.cancel()

        if to_cancel:
            results = await asyncio.gather(*to_cancel, return_exceptions=True)
            for task, result in zip(to_cancel, results, strict=False):
                if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                    self.logger.error(
                        "Background task ended with error during shutdown",
                        exc_info=result,
                        extra={"task_name": task.get_name()},
                    )

        self._tasks.clear()
        memory = getattr(getattr(self.container, "memory", None), "autonomous", None)
        if memory is not None and hasattr(memory, "shutdown"):
            await memory.shutdown()
            self.logger.info("Autonomous memory executor closed")
        self._discord_bot = None
        self._x_monitor = None
        self._live_agent = None

    def tasks(self) -> list[asyncio.Task[Any]]:
        return list(self._tasks)
