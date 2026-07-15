from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from noesis_agent.domain.contracts.runtime import HostDecision, HostIntent, ResponseMode, SessionContext


class ProviderCapability(str, Enum):
    TEXT_GENERATION = "text_generation"
    HOST_RESPONSE = "host_response"
    SUMMARY = "summary"
    MEMORY_AWARE = "memory_aware"
    MODERATION = "moderation"
    REALTIME_AUDIO = "realtime_audio"
    ELKA_COGNITION = "elka_cognition"
    LOCAL_FALLBACK = "local_fallback"


class CognitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(default_factory=lambda: uuid4().hex)
    session_id: str
    instruction: str = Field(min_length=1, max_length=6000)
    intent: HostIntent = HostIntent.ANSWER_DIRECTLY
    response_mode: ResponseMode = ResponseMode.SHORT
    context: str = Field(default="", max_length=16000)
    transcript_tail: str = Field(default="", max_length=16000)
    memories: list[str] = Field(default_factory=list)
    local_fallback: str = Field(default="", max_length=4000)
    session_context: SessionContext | None = None
    required_capabilities: list[ProviderCapability] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=180.0)


class CognitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    provider_name: str
    text: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    used_fallback: bool = False
    capabilities_used: list[ProviderCapability] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CognitionProviderStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_name: str
    available: bool
    capabilities: list[ProviderCapability] = Field(default_factory=list)
    reason: str = ""
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ResponseRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: HostDecision
    response_mode: ResponseMode
    cognition_request: CognitionRequest
    should_generate: bool = True
    reason: str = Field(default="", max_length=500)


__all__ = [
    "CognitionProviderStatus",
    "CognitionRequest",
    "CognitionResponse",
    "ProviderCapability",
    "ResponseRoute",
]
