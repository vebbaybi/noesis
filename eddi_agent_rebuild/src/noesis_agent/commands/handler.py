from __future__ import annotations

from typing import Any

from noesis_agent.commands.processors import (
    AnnounceCommand,
    ChatCommand,
    NFTInsightCommand,
    PlanEpisodeCommand,
    SoloSessionCommand,
    VoiceTestCommand,
)
from noesis_agent.utils.noesislogger import NoesisLogger


class CommandHandler:
    """Central command dispatcher for platform and API initiated commands."""

    def __init__(self) -> None:
        self.logger = NoesisLogger(
            logger_name="noesis_agent.commands.handler",
        ).logger

        announce = AnnounceCommand()
        chat = ChatCommand()
        plan = PlanEpisodeCommand()
        solo = SoloSessionCommand()
        voice_test = VoiceTestCommand()
        insight = NFTInsightCommand()

        self._processors = {
            "announce": announce,
            "chat": chat,
            "message": chat,
            "plan_episode": plan,
            "plan": plan,
            "start_solo": solo,
            "solo": solo,
            "voice_test": voice_test,
            "test_voice": voice_test,
            "nft_insight": insight,
            "insight": insight,
        }

    async def handle(self, command_name: str, payload: dict[str, Any] | None) -> str | None:
        command = str(command_name or "").strip().lower()
        normalized_payload = payload if isinstance(payload, dict) else {}

        processor = self._processors.get(command)
        if processor is None:
            self.logger.warning(
                "Unknown command received",
                extra={
                    "command": command,
                    "payload_keys": sorted(normalized_payload.keys()),
                },
            )
            return f"Unknown command: {command_name}"

        self.logger.info(
            "Processing command",
            extra={
                "command": command,
                "processor": processor.__class__.__name__,
            },
        )

        try:
            return await processor.execute(normalized_payload)
        except Exception as exc:
            self.logger.error(
                "Command execution failed",
                exc_info=exc,
                extra={
                    "command": command,
                    "processor": processor.__class__.__name__,
                },
            )
            return f"Error executing command: {str(exc)}"
