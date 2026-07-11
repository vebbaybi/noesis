from __future__ import annotations

from pathlib import Path

from noesis_agent.audio.tts_pipeline import TTSPipeline
from noesis_agent.brain.voice_profiles import VoiceProfile, VoiceProfileManager
from noesis_agent.clients.openai_client import OpenAIService


class VoiceService:
    def __init__(self, openai: OpenAIService, voice_profiles: VoiceProfileManager) -> None:
        self.openai = openai
        self.voice_profiles = voice_profiles
        self._pipelines: dict[str, TTSPipeline] = {}

    def create_profile(
        self,
        profile_id: str,
        *,
        display_name: str,
        preferred_openai_voice: str = "alloy",
        speaking_notes: str = "",
        humor_temperature: float = 0.7,
        pacing: float = 1.0,
    ) -> VoiceProfile:
        return self.voice_profiles.create_profile(
            profile_id,
            display_name=display_name,
            preferred_openai_voice=preferred_openai_voice,
            speaking_notes=speaking_notes,
            humor_temperature=humor_temperature,
            pacing=pacing,
        )

    def add_training_sample(self, profile_id: str, audio_path: str | Path, transcript: str = "") -> VoiceProfile:
        return self.voice_profiles.add_sample(profile_id, audio_path=audio_path, transcript=transcript)

    def get_profile(self, profile_id: str) -> VoiceProfile | None:
        return self.voice_profiles.get_profile(profile_id)

    def training_status(self, profile_id: str) -> dict[str, object]:
        return self.voice_profiles.evaluate_training_readiness(profile_id)

    async def speak(self, text: str, profile_id: str | None = None) -> bytes:
        voice = self.voice_profiles.resolve_voice(profile_id)
        speed = self.voice_profiles.resolve_speed(profile_id)
        pipeline = self._pipelines.get(voice)
        if pipeline is None:
            pipeline = TTSPipeline(self.openai, voice=voice)
            self._pipelines[voice] = pipeline
        return await pipeline.synthesize(text, speed=speed)
