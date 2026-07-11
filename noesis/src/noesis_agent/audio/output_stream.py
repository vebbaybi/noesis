from __future__ import annotations

import sounddevice as sd
import numpy as np


class SpeakerOutputStream:
    def __init__(self, samplerate: int = 24000) -> None:
        self.samplerate = samplerate

    def play(self, audio_bytes: bytes) -> None:
        data = np.frombuffer(audio_bytes, dtype=np.int16)
        sd.play(data, self.samplerate)
        sd.wait()
