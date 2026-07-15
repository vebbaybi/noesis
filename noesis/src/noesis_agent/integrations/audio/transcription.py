from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterable, List, Optional

import numpy as np

from noesis_agent.shared.noesislogger import NoesisLogger


@dataclass
class TranscriptSegment:
    text: str
    start: float
    end: float
    speaker: str | None = None


class TranscriptionPipeline:
    """Low-latency streaming transcription built on faster-whisper."""

    def __init__(
        self,
        model_size: str = "small.en",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "en",
    ) -> None:
        self.logger = NoesisLogger("noesis.audio.transcription").logger
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "Audio transcription requires the optional 'audio' dependencies. "
                "Install with: pip install -e \".[audio]\""
            ) from exc
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.language = language

    async def transcribe_chunk(self, pcm_bytes: bytes, sample_rate: int = 16000) -> list[TranscriptSegment]:
        """Transcribe a short PCM chunk (16-bit mono) into text segments."""
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if len(pcm_bytes) % 2:
            raise ValueError("PCM input must contain complete 16-bit samples")
        # Convert bytes to float32 numpy array in range [-1, 1]
        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        def _transcribe() -> list[TranscriptSegment]:
            segments_iter, _info = self.model.transcribe(
                audio, language=self.language, beam_size=1, temperature=0.2,
                vad_filter=True, vad_parameters={"min_silence_duration_ms": 250},
                word_timestamps=False,
            )
            # faster-whisper returns a lazy generator; consume it inside the worker.
            return [TranscriptSegment(text=segment.text.strip(), start=float(segment.start),
                                      end=float(segment.end)) for segment in segments_iter]

        segments = await asyncio.to_thread(_transcribe)

        if segments:
            self.logger.debug(
                "Transcription complete",
                extra={"segments": len(segments), "duration": segments[-1].end - segments[0].start},
            )

        return segments


class StreamingTranscriber:
    """Async helper to continuously transcribe audio fed into an asyncio.Queue."""

    def __init__(
        self,
        pipeline: TranscriptionPipeline,
        *,
        min_chunk_seconds: float = 1.5,
        sample_rate: int = 16000,
    ) -> None:
        self.pipeline = pipeline
        self.queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=64)
        self._running = False
        self._listeners: list[asyncio.Queue[list[TranscriptSegment]]] = []
        self.logger = NoesisLogger("noesis.audio.streaming_transcriber").logger
        self.min_chunk_bytes = max(2, int(min_chunk_seconds * sample_rate * 2))

    def add_listener(self) -> asyncio.Queue[list[TranscriptSegment]]:
        q: asyncio.Queue[list[TranscriptSegment]] = asyncio.Queue()
        self._listeners.append(q)
        return q

    async def push_audio(self, pcm_bytes: bytes) -> None:
        await self.queue.put(pcm_bytes)

    async def run(self) -> None:
        if self._running:
            return
        self._running = True
        self.logger.info("Streaming transcriber started")

        try:
            buffer = bytearray()
            while self._running:
                chunk = await self.queue.get()
                if chunk is None:
                    if buffer:
                        await self._transcribe_and_publish(bytes(buffer))
                    break

                buffer.extend(chunk)
                if len(buffer) < self.min_chunk_bytes:
                    continue

                await self._transcribe_and_publish(bytes(buffer))
                buffer.clear()
        finally:
            self._running = False
            self.logger.info("Streaming transcriber stopped")

    async def _transcribe_and_publish(self, chunk: bytes) -> None:
        segments = await self.pipeline.transcribe_chunk(chunk)
        if not segments:
            return

        for listener in list(self._listeners):
            await listener.put(segments)

    async def stop(self) -> None:
        self._running = False
        await self.queue.put(None)  # type: ignore[arg-type]


__all__ = ["TranscriptionPipeline", "TranscriptSegment", "StreamingTranscriber"]
