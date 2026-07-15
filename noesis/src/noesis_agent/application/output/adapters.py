from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from noesis_agent.application.ports import DisabledRuntimeOptions, RuntimeOptions
from noesis_agent.domain.contracts.live import HostOutput, OutputChannel, OutputDispatchResult, OutputStatus
from noesis_agent.shared.noesislogger import NoesisLogger


class OutputAdapter(Protocol):
    name: str

    def capabilities(self) -> list[OutputChannel]:
        ...

    def is_enabled(self, channel: OutputChannel) -> bool:
        ...

    async def dispatch(self, output: HostOutput, channel: OutputChannel) -> OutputDispatchResult:
        ...


class LocalTextOutputAdapter:
    """Local output adapter used by API-only and development host turns."""

    name = "local_text"

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.history: list[HostOutput] = []
        self.logger = NoesisLogger("noesis.output.local_text").logger

    def capabilities(self) -> list[OutputChannel]:
        return [OutputChannel.LOCAL_TEXT]

    def is_enabled(self, channel: OutputChannel) -> bool:
        return self.enabled and channel == OutputChannel.LOCAL_TEXT

    async def dispatch(self, output: HostOutput, channel: OutputChannel) -> OutputDispatchResult:
        if channel != OutputChannel.LOCAL_TEXT:
            return _dispatch_result(
                channel=channel,
                status=OutputStatus.UNSUPPORTED,
                adapter_name=self.name,
                output_id=output.output_id,
                message="Local text adapter only supports local_text output.",
            )
        if not self.enabled:
            return _dispatch_result(
                channel=channel,
                status=OutputStatus.DISABLED,
                adapter_name=self.name,
                output_id=output.output_id,
                message="Local text output is disabled.",
            )

        self.history.append(output)
        self.logger.info(
            "Local host output dispatched",
            extra={"session_id": output.session_id, "output_id": output.output_id, "length": len(output.text)},
        )
        return _dispatch_result(
            channel=channel,
            status=OutputStatus.SENT,
            adapter_name=self.name,
            output_id=output.output_id,
            message="Host output recorded by local text adapter.",
            delivered=True,
        )


class DiscordOutputAdapter:
    """Discord text and voice dispatcher using the existing bot/live-agent runtime objects."""

    name = "discord"

    def __init__(
        self,
        *,
        runtime_settings: RuntimeOptions | None = None,
        discord_client_getter: Callable[[], Any | None] | None = None,
        live_agent_getter: Callable[[], Any | None] | None = None,
    ) -> None:
        self.settings = runtime_settings or DisabledRuntimeOptions()
        self._discord_client_getter = discord_client_getter
        self._live_agent_getter = live_agent_getter
        self._discord_client: Any | None = None
        self.logger = NoesisLogger("noesis.output.discord").logger

    def bind_client(self, client: Any) -> None:
        self._discord_client = client

    def capabilities(self) -> list[OutputChannel]:
        return [OutputChannel.DISCORD_TEXT, OutputChannel.DISCORD_VOICE]

    def is_enabled(self, channel: OutputChannel) -> bool:
        if channel not in self.capabilities():
            return False
        return bool(getattr(self.settings, "enable_discord", False) and getattr(self.settings, "discord_bot_token", ""))

    async def dispatch(self, output: HostOutput, channel: OutputChannel) -> OutputDispatchResult:
        if channel not in self.capabilities():
            return _dispatch_result(
                channel=channel,
                status=OutputStatus.UNSUPPORTED,
                adapter_name=self.name,
                output_id=output.output_id,
                message="Discord adapter does not support the requested output channel.",
            )

        disabled = self._disabled_reason(channel)
        if disabled:
            return _dispatch_result(
                channel=channel,
                status=OutputStatus.DISABLED,
                adapter_name=self.name,
                output_id=output.output_id,
                message=disabled,
            )

        if channel == OutputChannel.DISCORD_TEXT:
            return await self._dispatch_text(output)
        return await self._dispatch_voice(output)

    def _disabled_reason(self, channel: OutputChannel) -> str:
        if not getattr(self.settings, "enable_discord", False):
            return "Discord output is disabled by configuration."
        if not getattr(self.settings, "discord_bot_token", ""):
            return "Discord output is enabled but DISCORD_BOT_TOKEN is not configured."
        if channel == OutputChannel.DISCORD_VOICE:
            if not getattr(self.settings, "discord_guild_id", None):
                return "Discord voice output requires DISCORD_GUILD_ID."
            if not getattr(self.settings, "discord_voice_channel_id", None):
                return "Discord voice output requires DISCORD_VOICE_CHANNEL_ID."
        return ""

    async def _dispatch_text(self, output: HostOutput) -> OutputDispatchResult:
        client = self._resolve_discord_client()
        if client is None or not _client_ready(client):
            return _dispatch_result(
                channel=OutputChannel.DISCORD_TEXT,
                status=OutputStatus.SKIPPED,
                adapter_name=self.name,
                output_id=output.output_id,
                message="Discord is configured, but no connected Discord client is available.",
            )

        channel = self._select_text_channel(client)
        if channel is None or not hasattr(channel, "send"):
            return _dispatch_result(
                channel=OutputChannel.DISCORD_TEXT,
                status=OutputStatus.SKIPPED,
                adapter_name=self.name,
                output_id=output.output_id,
                message="No Discord text channel is available for host output.",
            )

        try:
            message = await channel.send(output.text[:2000])
        except Exception as exc:
            self.logger.error("Discord text output failed", exc_info=exc)
            return _dispatch_result(
                channel=OutputChannel.DISCORD_TEXT,
                status=OutputStatus.FAILED,
                adapter_name=self.name,
                output_id=output.output_id,
                message="Discord text output failed.",
                error=str(exc),
            )

        return _dispatch_result(
            channel=OutputChannel.DISCORD_TEXT,
            status=OutputStatus.SENT,
            adapter_name=self.name,
            output_id=output.output_id,
            external_id=str(getattr(message, "id", "")) or None,
            message="Host output sent to Discord text.",
            delivered=True,
        )

    async def _dispatch_voice(self, output: HostOutput) -> OutputDispatchResult:
        live_agent = self._resolve_live_agent()
        if live_agent is None or not hasattr(live_agent, "speak_text"):
            return _dispatch_result(
                channel=OutputChannel.DISCORD_VOICE,
                status=OutputStatus.UNSUPPORTED,
                adapter_name=self.name,
                output_id=output.output_id,
                message="Discord voice output requires an active live media agent with speak_text support.",
            )

        try:
            result = live_agent.speak_text(output.text, topic=str(output.metadata.get("topic") or "NOESIS live turn"))
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            self.logger.error("Discord voice output failed", exc_info=exc)
            return _dispatch_result(
                channel=OutputChannel.DISCORD_VOICE,
                status=OutputStatus.FAILED,
                adapter_name=self.name,
                output_id=output.output_id,
                message="Discord voice output failed.",
                error=str(exc),
            )

        return _dispatch_result(
            channel=OutputChannel.DISCORD_VOICE,
            status=OutputStatus.SENT,
            adapter_name=self.name,
            output_id=output.output_id,
            message=str(result or "Host output sent to Discord voice."),
            delivered=True,
        )

    def _resolve_discord_client(self) -> Any | None:
        if self._discord_client is not None:
            return self._discord_client
        if self._discord_client_getter is None:
            return None
        return self._discord_client_getter()

    def _resolve_live_agent(self) -> Any | None:
        if self._live_agent_getter is None:
            return None
        return self._live_agent_getter()

    def _select_text_channel(self, client: Any) -> Any | None:
        for channel_id in getattr(self.settings, "discord_allowed_text_channel_ids", []) or []:
            channel = _get_channel(client, int(channel_id))
            if channel is not None and hasattr(channel, "send"):
                return channel

        guild_id = getattr(self.settings, "discord_guild_id", None)
        guild = client.get_guild(int(guild_id)) if guild_id and hasattr(client, "get_guild") else None
        system_channel = getattr(guild, "system_channel", None)
        if system_channel is not None and hasattr(system_channel, "send"):
            return system_channel
        return None


def _get_channel(client: Any, channel_id: int) -> Any | None:
    if not hasattr(client, "get_channel"):
        return None
    return client.get_channel(channel_id)


def _client_ready(client: Any) -> bool:
    is_ready = getattr(client, "is_ready", None)
    if callable(is_ready):
        return bool(is_ready())
    return bool(getattr(client, "ready", False))


def _dispatch_result(
    *,
    channel: OutputChannel,
    status: OutputStatus,
    adapter_name: str,
    output_id: str | None,
    message: str,
    external_id: str | None = None,
    error: str | None = None,
    delivered: bool = False,
) -> OutputDispatchResult:
    return OutputDispatchResult(
        channel=channel,
        status=status,
        adapter_name=adapter_name,
        output_id=output_id,
        external_id=external_id,
        error=error,
        message=message,
        delivered_at=datetime.now(timezone.utc) if delivered else None,
    )


__all__ = [
    "DiscordOutputAdapter",
    "LocalTextOutputAdapter",
    "OutputAdapter",
]
