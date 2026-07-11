from __future__ import annotations

from typing import Literal

from noesis_agent.clients.openai_client import OpenAIService
from noesis_agent.utils.noesislogger import NoesisLogger


class TTSPipeline:
    """High quality text-to-speech backed by OpenAI TTS models."""

    def __init__(
        self,
        openai_service: OpenAIService,
        *,
        voice: str = "alloy",
        format: Literal["mp3", "wav"] = "wav",
    ) -> None:
        self.openai = openai_service
        self.voice = voice
        self.format = format
        self.logger = NoesisLogger("noesis.audio.tts").logger

    async def synthesize(self, text: str, *, speed: float = 1.0) -> bytes:
        if not self.openai.is_enabled():
            raise RuntimeError("OpenAI not configured for TTS")

        if not text.strip():
            raise ValueError("Cannot synthesize empty text")

        resp = await self.openai.client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice=self.voice,
            input=text,
            speed=float(speed),
            response_format=self.format,
        )

        audio_bytes = await resp.aread()
        self.logger.debug(
            "TTS synthesized",
            extra={"bytes": len(audio_bytes), "voice": self.voice, "format": self.format},
        )
        return audio_bytes


__all__ = ["TTSPipeline"]
