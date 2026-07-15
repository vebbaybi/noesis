from __future__ import annotations


class VoiceActivityDetector:
    def __init__(self, aggressiveness: int = 2) -> None:
        if aggressiveness not in range(4):
            raise ValueError("VAD aggressiveness must be between 0 and 3")
        try:
            import webrtcvad
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError('Voice activity detection requires the "audio" extra') from exc
        self.vad = webrtcvad.Vad(aggressiveness)

    def is_speech(self, audio_bytes: bytes, sample_rate: int = 16000) -> bool:
        if sample_rate not in {8000, 16000, 32000, 48000}:
            raise ValueError("WebRTC VAD supports 8, 16, 32, or 48 kHz PCM")
        sample_width = 2
        duration_ms = len(audio_bytes) * 1000 / (sample_rate * sample_width)
        if duration_ms not in {10.0, 20.0, 30.0}:
            raise ValueError("WebRTC VAD requires one 10, 20, or 30 ms 16-bit mono PCM frame")
        return self.vad.is_speech(audio_bytes, sample_rate)
