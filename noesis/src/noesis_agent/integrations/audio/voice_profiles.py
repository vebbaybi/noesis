from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import wave

from noesis_agent.infrastructure.persistence.json_store import JsonStore


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class VoiceSample:
    audio_path: str
    transcript: str = ""
    duration_seconds: float | None = None
    sample_rate: int | None = None
    channels: int | None = None
    size_bytes: int = 0
    added_at: str = field(default_factory=_utc_now)


@dataclass
class VoiceProfile:
    profile_id: str
    display_name: str
    preferred_openai_voice: str = "alloy"
    speaking_notes: str = ""
    humor_temperature: float = 0.7
    pacing: float = 1.0
    samples: list[VoiceSample] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    ready_for_training: bool = False
    training_status: str = "collecting"
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)


class VoiceProfileManager:
    def __init__(self, store: JsonStore, data_dir: Path) -> None:
        self.store = store
        self.data_dir = Path(data_dir)
        (self.data_dir / "voice").mkdir(parents=True, exist_ok=True)

    def _serialize(self, profile: VoiceProfile) -> dict:
        payload = asdict(profile)
        payload["samples"] = [asdict(sample) for sample in profile.samples]
        return payload

    def _deserialize(self, payload: dict) -> VoiceProfile:
        samples = [VoiceSample(**sample) for sample in payload.get("samples", [])]
        payload = dict(payload)
        payload["samples"] = samples
        return VoiceProfile(**payload)

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
        profile = VoiceProfile(
            profile_id=profile_id,
            display_name=display_name,
            preferred_openai_voice=preferred_openai_voice,
            speaking_notes=speaking_notes,
            humor_temperature=max(0.0, min(1.0, float(humor_temperature))),
            pacing=max(0.8, min(1.25, float(pacing))),
        )
        self.store.write("voice_profiles", profile_id, self._serialize(profile))
        return profile

    def get_profile(self, profile_id: str) -> VoiceProfile | None:
        payload = self.store.read("voice_profiles", profile_id)
        if not payload:
            return None
        return self._deserialize(payload)

    def list_profiles(self) -> list[VoiceProfile]:
        profiles: list[VoiceProfile] = []
        for key in self.store.list_keys("voice_profiles"):
            profile = self.get_profile(key)
            if profile:
                profiles.append(profile)
        return profiles

    def add_sample(self, profile_id: str, audio_path: str | Path, transcript: str = "") -> VoiceProfile:
        profile = self.get_profile(profile_id)
        if profile is None:
            raise KeyError(f"Voice profile not found: {profile_id}")

        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(path)

        duration_seconds: float | None = None
        sample_rate: int | None = None
        channels: int | None = None
        if path.suffix.lower() == ".wav":
            with wave.open(str(path), "rb") as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                if sample_rate:
                    duration_seconds = round(frames / float(sample_rate), 3)

        sample = VoiceSample(
            audio_path=str(path.resolve()),
            transcript=transcript.strip(),
            duration_seconds=duration_seconds,
            sample_rate=sample_rate,
            channels=channels,
            size_bytes=path.stat().st_size,
        )
        profile.samples.append(sample)
        self._refresh_status(profile)
        self.store.write("voice_profiles", profile.profile_id, self._serialize(profile))
        return profile

    def _refresh_status(self, profile: VoiceProfile) -> None:
        profile.total_duration_seconds = round(
            sum(sample.duration_seconds or 0.0 for sample in profile.samples),
            3,
        )
        transcribed_count = sum(1 for sample in profile.samples if sample.transcript.strip())
        profile.ready_for_training = (
            len(profile.samples) >= 3
            and profile.total_duration_seconds >= 45.0
            and transcribed_count >= 2
        )
        profile.training_status = "ready_for_training" if profile.ready_for_training else "collecting"
        profile.updated_at = _utc_now()

    def evaluate_training_readiness(self, profile_id: str) -> dict[str, object]:
        profile = self.get_profile(profile_id)
        if profile is None:
            raise KeyError(f"Voice profile not found: {profile_id}")

        transcribed_count = sum(1 for sample in profile.samples if sample.transcript.strip())
        return {
            "profile_id": profile.profile_id,
            "sample_count": len(profile.samples),
            "transcribed_count": transcribed_count,
            "total_duration_seconds": profile.total_duration_seconds,
            "ready_for_training": profile.ready_for_training,
            "training_status": profile.training_status,
        }

    def build_style_prompt(self, profile_id: str | None) -> str:
        if not profile_id:
            return ""

        profile = self.get_profile(profile_id)
        if profile is None:
            return ""

        notes = profile.speaking_notes.strip() or "clear, quick, conversational delivery"
        return (
            f"Voice profile: {profile.display_name}. "
            f"Speaking notes: {notes}. "
            f"Pacing target: {profile.pacing:.2f}. "
            f"Humor temperature: {profile.humor_temperature:.2f}."
        )

    def resolve_voice(self, profile_id: str | None) -> str:
        if not profile_id:
            return "alloy"
        profile = self.get_profile(profile_id)
        if profile is None:
            return "alloy"
        return profile.preferred_openai_voice or "alloy"

    def resolve_speed(self, profile_id: str | None) -> float:
        if not profile_id:
            return 1.0
        profile = self.get_profile(profile_id)
        if profile is None:
            return 1.0
        return profile.pacing


__all__ = ["VoiceProfile", "VoiceProfileManager", "VoiceSample"]
