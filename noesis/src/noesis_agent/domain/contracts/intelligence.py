from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class CapabilityState(str, Enum):
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    LOADING = "loading"
    READY = "ready"
    DEGRADED = "degraded"
    FAILED = "failed"
    CREDENTIAL_BLOCKED = "credential_blocked"
    HARDWARE_BLOCKED = "hardware_blocked"


class FailureCategory(str, Enum):
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    RATE_LIMIT = "rate_limit"
    OVERLOAD = "overload"
    SERVER = "server"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    INVALID_REQUEST = "invalid_request"
    MALFORMED_RESPONSE = "malformed_response"
    CONTENT_POLICY = "content_policy"
    TOOL_VALIDATION = "tool_validation"
    CANCELLED = "cancelled"
    INTERNAL = "internal"


class ModerationDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class ModerationAction(str, Enum):
    ALLOW = "allow"
    REDACT = "allow_with_redaction"
    WARN = "warn"
    BLOCK = "block"
    ESCALATE = "escalate"
    LOG_ONLY = "log_only"
    DEFER = "defer_unavailable"


class ModerationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision_id: str = Field(default_factory=lambda: uuid4().hex)
    tenant_id: str = Field(min_length=1, max_length=200)
    direction: ModerationDirection
    action: ModerationAction
    lexical_categories: list[str] = Field(default_factory=list)
    toxicity_scores: dict[str, float] = Field(default_factory=dict)
    triggered_categories: list[str] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(default_factory=dict)
    policy_version: str = "1"
    model_version: str = "unavailable"
    evidence: list[str] = Field(default_factory=list)
    failure: FailureCategory | None = None
    review_eligible: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DirectResponse(BaseModel):
    kind: Literal["direct_response"] = "direct_response"
    text: str = Field(min_length=1, max_length=12000)


class ToolCall(BaseModel):
    kind: Literal["tool_call"] = "tool_call"
    tool_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,63}$")
    arguments: dict[str, object] = Field(default_factory=dict)


class Clarification(BaseModel):
    kind: Literal["clarification"] = "clarification"
    question: str = Field(min_length=1, max_length=1000)


class Refusal(BaseModel):
    kind: Literal["refusal"] = "refusal"
    reason: str = Field(min_length=1, max_length=1000)


StructuredOutcome = Annotated[DirectResponse | ToolCall | Clarification | Refusal, Field(discriminator="kind")]


class IntelligenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=1, max_length=300)
    correlation_id: str = Field(default_factory=lambda: uuid4().hex)
    tenant_id: str = Field(min_length=1, max_length=200)
    user_id: str = Field(min_length=1, max_length=200)
    conversation_id: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=16000)
    authorized_capabilities: frozenset[str] = Field(default_factory=frozenset)
    local_only: bool = False


class RetrievalItem(BaseModel):
    point_id: str
    tenant_id: str
    text: str
    score: float = Field(ge=0.0, le=1.0)
    source_id: str
    provenance: str


class IntelligenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    correlation_id: str
    outcome: StructuredOutcome
    provider: str
    used_fallback: bool = False
    retrieved: list[RetrievalItem] = Field(default_factory=list)
    inbound_moderation: ModerationDecision
    outbound_moderation: ModerationDecision | None = None
    degraded_capabilities: list[str] = Field(default_factory=list)


class CapabilityHealth(BaseModel):
    name: str
    state: CapabilityState
    detail: str = ""


__all__ = [
    "CapabilityHealth", "CapabilityState", "Clarification", "DirectResponse",
    "FailureCategory", "IntelligenceRequest", "IntelligenceResult", "ModerationAction",
    "ModerationDecision", "ModerationDirection", "Refusal", "RetrievalItem",
    "StructuredOutcome", "ToolCall",
]
