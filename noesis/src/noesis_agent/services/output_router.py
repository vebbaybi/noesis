from __future__ import annotations

from noesis_agent.config.settings import Settings, settings
from noesis_agent.models.live import HostOutput, OutputChannel, OutputDispatchResult, OutputStatus
from noesis_agent.models.session import SessionState
from noesis_agent.services.output_adapters import DiscordOutputAdapter, LocalTextOutputAdapter
from noesis_agent.utils.noesislogger import NoesisLogger


class OutputRouter:
    """Selects enabled output adapters for a host turn and reports true delivery status."""

    def __init__(
        self,
        *,
        runtime_settings: Settings = settings,
        local_adapter: LocalTextOutputAdapter | None = None,
        discord_adapter: DiscordOutputAdapter | None = None,
    ) -> None:
        self.settings = runtime_settings
        self.local_adapter = local_adapter or LocalTextOutputAdapter()
        self.discord_adapter = discord_adapter or DiscordOutputAdapter(runtime_settings=runtime_settings)
        self.logger = NoesisLogger("noesis.output.router").logger

    def bind_discord_client(self, client) -> None:
        self.discord_adapter.bind_client(client)

    def select_channels(self, state: SessionState) -> list[OutputChannel]:
        room_platform = state.session.room_state.platform
        session_platform = state.session.primary_platform
        if (
            (room_platform == "discord" or session_platform == "discord")
            and getattr(self.settings, "enable_discord", False)
            and getattr(self.settings, "discord_bot_token", "")
        ):
            return [OutputChannel.DISCORD_TEXT]
        return [OutputChannel.LOCAL_TEXT]

    async def dispatch(self, output: HostOutput, state: SessionState) -> list[OutputDispatchResult]:
        channels = output.channels or self.select_channels(state)
        results: list[OutputDispatchResult] = []
        seen: set[OutputChannel] = set()

        for channel in channels:
            if channel in seen:
                continue
            seen.add(channel)

            if channel == OutputChannel.API_RESPONSE_ONLY:
                results.append(
                    OutputDispatchResult(
                        channel=channel,
                        status=OutputStatus.SKIPPED,
                        adapter_name="api_response",
                        output_id=output.output_id,
                        message="No external dispatch requested; host text is returned in the API/service result.",
                    )
                )
            elif channel == OutputChannel.LOCAL_TEXT:
                results.append(await self.local_adapter.dispatch(output, channel))
            elif channel in {OutputChannel.DISCORD_TEXT, OutputChannel.DISCORD_VOICE}:
                results.append(await self.discord_adapter.dispatch(output, channel))
            else:
                results.append(
                    OutputDispatchResult(
                        channel=channel,
                        status=OutputStatus.UNSUPPORTED,
                        adapter_name="output_router",
                        output_id=output.output_id,
                        message="No output adapter supports the requested channel.",
                    )
                )

        self.logger.info(
            "Host output dispatch complete",
            extra={
                "session_id": output.session_id,
                "output_id": output.output_id,
                "channels": [item.channel.value for item in results],
                "statuses": [item.status.value for item in results],
            },
        )
        return results


__all__ = ["OutputRouter"]
