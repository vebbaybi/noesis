from __future__ import annotations

import sys
import wave
from types import SimpleNamespace

import numpy as np
import pytest

from noesis_agent.integrations.audio.recording import AudioRecorder
from noesis_agent.integrations.audio.transcription import TranscriptionPipeline
from noesis_agent.integrations.audio.vad import VoiceActivityDetector
from noesis_agent.memory.semantic_memory import SemanticMemory


def test_semantic_memory_finds_paraphrased_topic_instead_of_exact_key_only() -> None:
    memory = SemanticMemory()
    memory.add("database selection", "The team selected PostgreSQL for production.", confidence=.9)
    memory.add("release schedule", "Version one ships on August 3.", confidence=.9)
    matches = memory.search_records("which database did the team select")
    assert matches
    assert matches[0].topic == "database selection"


def test_vad_validates_native_web_rtc_frame_contract(monkeypatch) -> None:
    fake = SimpleNamespace(Vad=lambda _level: SimpleNamespace(is_speech=lambda _data, _rate: True))
    monkeypatch.setitem(sys.modules, "webrtcvad", fake)
    detector = VoiceActivityDetector(2)
    assert detector.is_speech(bytes(640), 16000) is True  # 20 ms, mono int16
    with pytest.raises(ValueError, match="10, 20, or 30"):
        detector.is_speech(bytes(500), 16000)
    with pytest.raises(ValueError, match="supports"):
        detector.is_speech(bytes(640), 44100)


@pytest.mark.asyncio
async def test_whisper_generator_is_consumed_off_event_loop() -> None:
    class Model:
        def transcribe(self, *_args, **_kwargs):
            return iter([SimpleNamespace(text=" hello ", start=0.0, end=.4)]), object()

    pipeline = object.__new__(TranscriptionPipeline)
    pipeline.model = Model()
    pipeline.language = "en"
    pipeline.logger = SimpleNamespace(debug=lambda *_args, **_kwargs: None)
    result = await pipeline.transcribe_chunk(bytes(3200), sample_rate=16000)
    assert [(item.text, item.start, item.end) for item in result] == [("hello", 0.0, .4)]


def test_recorder_writes_real_wav_and_neutralizes_path_traversal(tmp_path, monkeypatch) -> None:
    class SoundFile:
        @staticmethod
        def write(path, samples, sample_rate, **_kwargs):
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(sample_rate)
                handle.writeframes(np.asarray(samples, dtype=np.int16).tobytes())

    monkeypatch.setitem(sys.modules, "soundfile", SoundFile)
    path = AudioRecorder(tmp_path).save("../../unsafe session", bytes(320), sample_rate=16000)
    assert path.parent == tmp_path
    with wave.open(str(path), "rb") as handle:
        assert handle.getframerate() == 16000
        assert handle.getnchannels() == 1
