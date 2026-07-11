from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RealtimeVoiceTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voice: str = "alloy"
    instructions: str = Field(default="You are a sharp, clear, high-energy Web3 host.")
    temperature: float = Field(default=0.8, ge=0.0, le=1.2)
    session_id: str | None = None
    language: str = "en"


class RealtimeVoiceTokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    url: str = "wss://api.openai.com/v1/realtime"
    expires_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)


class VoiceTrainingSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audio_path: str
    transcript: str = ""
    duration_seconds: float | None = None
    sample_rate: int | None = None
    channels: int | None = None
    size_bytes: int = 0


class VoiceTrainingStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    sample_count: int = 0
    transcribed_count: int = 0
    total_duration_seconds: float = 0.0
    ready_for_training: bool = False
    training_status: str = "collecting"


__all__ = [
    "RealtimeVoiceTokenRequest",
    "RealtimeVoiceTokenResponse",
    "VoiceTrainingSample",
    "VoiceTrainingStatus",
]
