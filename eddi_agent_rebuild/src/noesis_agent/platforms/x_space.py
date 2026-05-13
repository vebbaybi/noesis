from __future__ import annotations

from noesis_agent.clients.x_client import XClient
from noesis_agent.platforms.base import AudioCallback
from noesis_agent.utils.noesislogger import NoesisLogger


class XSpaceAdapter:
    """Lightweight wrapper to post text updates to X during a Space."""

    def __init__(self, client: XClient) -> None:
        self.client = client
        self.logger = NoesisLogger("noesis.platforms.x_space").logger
        self._audio_consumer: AudioCallback | None = None

    def register_audio_consumer(self, consumer: AudioCallback) -> None:
        self._audio_consumer = consumer

    async def join(self, *, session_id: str) -> None:
        self.logger.info("Joined X context (posting mode only)", extra={"session_id": session_id})

    async def leave(self) -> None:
        self.logger.info("Left X context")

    async def send_text(self, text: str) -> None:
        result = self.client.post(text=text, dry_run=not self.client.is_enabled())
        self.logger.info("X text send completed", extra={"status": result.get("status")})

    async def send_audio(self, audio_bytes: bytes, *, sample_rate: int = 24000) -> None:
        self.logger.info("Audio send not supported for X; skipping")
