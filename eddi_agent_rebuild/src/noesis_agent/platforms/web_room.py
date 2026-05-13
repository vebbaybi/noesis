from __future__ import annotations

from noesis_agent.platforms.base import AudioCallback
from noesis_agent.utils.noesislogger import NoesisLogger


class WebRoomAdapter:
    def __init__(self) -> None:
        self.logger = NoesisLogger("noesis.platforms.web_room").logger
        self._audio_consumer: AudioCallback | None = None

    def register_audio_consumer(self, consumer: AudioCallback) -> None:
        self._audio_consumer = consumer

    async def join(self, *, session_id: str) -> None:
        self.logger.info("Web room ready", extra={"session_id": session_id})

    async def leave(self) -> None:
        self.logger.info("Web room closed")

    async def send_text(self, text: str) -> None:
        self.logger.info("Web room message", extra={"text": text})

    async def send_audio(self, audio_bytes: bytes, *, sample_rate: int = 24000) -> None:
        self.logger.info("Web room audio send not implemented")
