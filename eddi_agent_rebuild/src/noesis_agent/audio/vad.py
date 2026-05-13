from __future__ import annotations

import webrtcvad


class VoiceActivityDetector:
    def __init__(self, aggressiveness: int = 2) -> None:
        self.vad = webrtcvad.Vad(aggressiveness)

    def is_speech(self, audio_bytes: bytes, sample_rate: int = 16000) -> bool:
        return self.vad.is_speech(audio_bytes, sample_rate)
