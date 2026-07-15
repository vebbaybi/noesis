"""Audio package with lazy optional-dependency loading.

Importing core Noesis cognition must not require microphone, VAD, or Whisper packages.
"""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "TranscriptionPipeline": ("transcription", "TranscriptionPipeline"),
    "StreamingTranscriber": ("transcription", "StreamingTranscriber"),
    "TranscriptSegment": ("transcription", "TranscriptSegment"),
    "SpeakerDiarizer": ("diarization", "SpeakerDiarizer"),
    "SpeakerTurn": ("diarization", "SpeakerTurn"),
    "TTSPipeline": ("tts_pipeline", "TTSPipeline"),
    "MicrophoneInputStream": ("input_stream", "MicrophoneInputStream"),
    "SpeakerOutputStream": ("output_stream", "SpeakerOutputStream"),
    "AudioMixer": ("mixer", "AudioMixer"),
    "VoiceActivityDetector": ("vad", "VoiceActivityDetector"),
    "add_filler": ("prosody", "add_filler"),
    "Soundboard": ("soundboard", "Soundboard"),
    "reduce_noise": ("noise_reduction", "reduce_noise"),
    "AudioRecorder": ("recording", "AudioRecorder"),
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attribute = _EXPORTS[name]
    value = getattr(import_module(f"{__name__}.{module_name}"), attribute)
    globals()[name] = value
    return value


__all__ = list(_EXPORTS)
