from __future__ import annotations

import numpy as np


class SpeakerOutputStream:
    def __init__(self, samplerate: int = 24000) -> None:
        self.samplerate = samplerate

    def play(self, audio_bytes: bytes) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise RuntimeError('Speaker output requires the "audio" extra') from exc
        data = np.frombuffer(audio_bytes, dtype=np.int16)
        sd.play(data, self.samplerate)
        sd.wait()
