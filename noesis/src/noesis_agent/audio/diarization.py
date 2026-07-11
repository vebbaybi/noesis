from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from noesis_agent.utils.noesislogger import NoesisLogger


@dataclass
class SpeakerTurn:
    speaker: str
    start: float
    end: float


class SpeakerDiarizer:
    """Wrapper around pyannote speaker diarization with graceful fallback."""

    def __init__(self, model_name: str = "pyannote/speaker-diarization-3.1") -> None:
        self.logger = NoesisLogger("noesis.audio.diarization").logger
        try:
            from pyannote.audio import Pipeline  # type: ignore

            auth_token = os.getenv("PYANNOTE_AUTH_TOKEN")
            kwargs = {"use_auth_token": auth_token} if auth_token else {}
            self.pipeline = Pipeline.from_pretrained(model_name, **kwargs)
            self.available = True
            self.logger.info("pyannote diarization model loaded", extra={"model": model_name})
        except Exception as exc:  # pragma: no cover - optional dependency path
            self.pipeline = None
            self.available = False
            self.logger.warning("pyannote not available; diarization disabled", extra={"error": str(exc)})

    async def diarize(self, pcm_bytes: bytes, sample_rate: int = 16000) -> list[SpeakerTurn]:
        if not self.available:
            # return single anonymous speaker block as fallback
            duration_seconds = len(pcm_bytes) / 2 / sample_rate
            return [SpeakerTurn(speaker="unknown", start=0.0, end=duration_seconds)]

        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        def _run():
            return self.pipeline({"waveform": audio, "sample_rate": sample_rate})

        loop = asyncio.get_running_loop()
        diarization = await loop.run_in_executor(None, _run)

        turns: list[SpeakerTurn] = []
        for i, (segment, _, speaker) in enumerate(diarization.itertracks(yield_label=True)):
            turns.append(
                SpeakerTurn(
                    speaker=str(speaker or f"spk_{i}"),
                    start=float(segment.start),
                    end=float(segment.end),
                )
            )

        return turns


__all__ = ["SpeakerDiarizer", "SpeakerTurn"]
