from __future__ import annotations

from noesis_agent.integrations.base import AudioCallback
from noesis_agent.shared.noesislogger import NoesisLogger


class YouTubeLiveAdapter:
    def __init__(self) -> None:
        self.logger = NoesisLogger("noesis.platforms.youtube").logger
        self._audio_consumer: AudioCallback | None = None

    def register_audio_consumer(self, consumer: AudioCallback) -> None:
        self._audio_consumer = consumer

    async def join(self, *, session_id: str) -> None:
        self.logger.info("YouTube Live adapter initialized (no-op without API keys)", extra={"session_id": session_id})

    async def leave(self) -> None:
        self.logger.info("YouTube Live adapter stopped")

    async def send_text(self, text: str) -> None:
        self.logger.info("YouTube chat send not implemented in this build")

    async def send_audio(self, audio_bytes: bytes, *, sample_rate: int = 24000) -> None:
        self.logger.info("YouTube audio send not supported")
