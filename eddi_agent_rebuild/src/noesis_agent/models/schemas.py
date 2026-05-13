from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from noesis_agent.models.analytics import AnalyticsSnapshot, EngagementSnapshot, LatencyMetric, TokenUsageSnapshot
from noesis_agent.models.auth import ApiKeyIdentity, AuthContext
from noesis_agent.models.cognition import CognitionProviderStatus, CognitionRequest, CognitionResponse, ProviderCapability
from noesis_agent.models.command import CommandExecutionResult, CommandIntent, ParsedCommand
from noesis_agent.models.events import EventEnvelope, SessionLifecycleEvent
from noesis_agent.models.guest import Guest
from noesis_agent.models.knowledge import ResearchBrief, ResearchFinding, ResearchSource
from noesis_agent.models.live import (
    HostOutput,
    HostTurnRequest,
    HostTurnResult,
    LiveEventIngestionResult,
    LiveEventType,
    LiveSessionEventRequest,
    OutputChannel,
    OutputDispatchResult,
    OutputStatus,
)
from noesis_agent.models.media import ClipMarker, MediaAsset, PostShowArtifacts, PublishingManifest, SessionSummary
from noesis_agent.models.memory import EpisodicMemoryRecord, GuestMemoryRecord, MemoryEntry, SemanticFact
from noesis_agent.models.moderation import ModerationQueueItem, ModerationReport
from noesis_agent.models.persona import (
    HostReply,
    HostReplyContext,
    HostReplyRequest,
    HostReplyResponse,
    PersonaProfile,
    ToneProfile,
)
from noesis_agent.models.platforms import PlatformAnnouncement, QuickTweetRequest, XPostRequest
from noesis_agent.models.runtime import (
    ActionItem,
    AudienceSignal,
    HostDecision,
    HostIntent,
    ResponseMode,
    RoomState,
    SessionContext,
    SpeakerState,
    TopicPlan,
)
from noesis_agent.models.session import Session, SessionCreateRequest, SessionPlatformState, SessionState
from noesis_agent.models.transcript import (
    SessionTranscriptEvent,
    TranscriptEvent,
    TranscriptEventType,
    TranscriptSignal,
)
from noesis_agent.models.types import (
    ChainId,
    LengthPreset,
    Platform,
    PlatformStatus,
    RecordingStatus,
    SessionStatus,
    SpeakerRole,
    normalize_platform,
)
from noesis_agent.models.voice import (
    RealtimeVoiceTokenRequest,
    RealtimeVoiceTokenResponse,
    VoiceTrainingSample,
    VoiceTrainingStatus,
)
from noesis_agent.models.web3 import MarketSignal, NFTCollectionMention, TokenMention, Web3EntityMention


class Topic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=120)
    angle: str = Field(default="", max_length=280)
    priority: int = Field(default=1, ge=1, le=100)
    duration_goal_minutes: int | None = Field(default=None, ge=2, le=45)
    speakers: list[str] | None = None


class EpisodePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    show_title: str = Field(min_length=3, max_length=140)
    platform: Platform = "dual"
    objective: str = Field(max_length=500)
    target_audience: str = Field(max_length=300)
    topics: list[Topic] = Field(min_length=1)
    duration_minutes: int = Field(default=60, ge=15, le=240)
    preferred_start_time: datetime | None = None
    hosts: list[str] = Field(default_factory=list)
    guests: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    rundown: list[dict[str, Any]] = Field(default_factory=list)
    opening_script: str = ""
    closing_script: str = ""

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform_value(cls, value: Any) -> str:
        return normalize_platform(value)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_audience(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        payload = dict(value)
        if "target_audience" not in payload and "audience" in payload:
            payload["target_audience"] = payload.pop("audience")
        return payload


class EpisodePlan(EpisodePlanRequest):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str | None = None
    version: int = 1
    active: bool = True

    @computed_field
    @property
    def short_id(self) -> str:
        return self.plan_id[:8]

    @computed_field
    @property
    def audience(self) -> str:
        return self.target_audience


RealtimeTokenRequest = RealtimeVoiceTokenRequest
RealtimeTokenResponse = RealtimeVoiceTokenResponse
SessionSummaryRequest = SessionSummary


__all__ = [
    "AnalyticsSnapshot",
    "ApiKeyIdentity",
    "AuthContext",
    "ChainId",
    "ClipMarker",
    "CognitionProviderStatus",
    "CognitionRequest",
    "CognitionResponse",
    "CommandExecutionResult",
    "CommandIntent",
    "EngagementSnapshot",
    "EpisodePlan",
    "EpisodePlanRequest",
    "EpisodicMemoryRecord",
    "EventEnvelope",
    "Guest",
    "GuestMemoryRecord",
    "HostReply",
    "HostDecision",
    "HostReplyContext",
    "HostReplyRequest",
    "HostReplyResponse",
    "HostIntent",
    "HostOutput",
    "LatencyMetric",
    "LengthPreset",
    "LiveEventIngestionResult",
    "LiveEventType",
    "LiveSessionEventRequest",
    "MarketSignal",
    "MediaAsset",
    "MemoryEntry",
    "ModerationQueueItem",
    "ModerationReport",
    "NFTCollectionMention",
    "ParsedCommand",
    "PersonaProfile",
    "OutputChannel",
    "OutputDispatchResult",
    "OutputStatus",
    "Platform",
    "PlatformAnnouncement",
    "PlatformStatus",
    "PostShowArtifacts",
    "ProviderCapability",
    "PublishingManifest",
    "QuickTweetRequest",
    "RealtimeTokenRequest",
    "RealtimeTokenResponse",
    "RealtimeVoiceTokenRequest",
    "RealtimeVoiceTokenResponse",
    "RecordingStatus",
    "ResearchBrief",
    "ResearchFinding",
    "ResearchSource",
    "ResponseMode",
    "SemanticFact",
    "RoomState",
    "Session",
    "SessionContext",
    "SessionCreateRequest",
    "SessionLifecycleEvent",
    "SessionPlatformState",
    "SessionState",
    "SessionStatus",
    "SessionSummary",
    "SessionSummaryRequest",
    "SessionTranscriptEvent",
    "HostTurnRequest",
    "HostTurnResult",
    "ActionItem",
    "AudienceSignal",
    "SpeakerRole",
    "SpeakerState",
    "TokenMention",
    "TokenUsageSnapshot",
    "ToneProfile",
    "Topic",
    "TopicPlan",
    "TranscriptEvent",
    "TranscriptEventType",
    "TranscriptSignal",
    "VoiceTrainingSample",
    "VoiceTrainingStatus",
    "Web3EntityMention",
    "XPostRequest",
    "normalize_platform",
]
