from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ComponentType(str, Enum):
    SIDE_EFFECT_CONFIRMATION = "side_effect_confirmation"
    MODERATION_REVIEW = "moderation_review"
    MEMORY_REVIEW = "memory_review"
    FAILED_ACTION_RETRY = "failed_action_retry"


class ComponentState(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"


class ComponentAction(str, Enum):
    CONFIRM = "confirm"
    CANCEL = "cancel"
    APPROVE = "approve"
    REJECT = "reject"
    RETAIN = "retain"
    REMOVE = "remove"
    RETRY = "retry"


class PersistentComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    component_id: str = Field(default_factory=lambda: uuid4().hex)
    component_type: ComponentType
    version: int = 1
    tenant_id: str = Field(min_length=1, max_length=200)
    authorized_user_ids: frozenset[str] = Field(default_factory=frozenset)
    authorized_role_ids: frozenset[str] = Field(default_factory=frozenset)
    operation: str = Field(min_length=1, max_length=100)
    resource_id: str = Field(min_length=1, max_length=300)
    expires_at: datetime
    state: ComponentState = ComponentState.PENDING
    idempotency_key: str = Field(min_length=1, max_length=300)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    audit_result: str = Field(default="", max_length=500)


class ComponentInteraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    component_id: str
    tenant_id: str
    user_id: str
    role_ids: frozenset[str] = Field(default_factory=frozenset)
    action: ComponentAction


class ComponentOutcome(BaseModel):
    component_id: str
    accepted: bool
    state: ComponentState
    message: str


__all__ = [
    "ComponentAction", "ComponentInteraction", "ComponentOutcome", "ComponentState",
    "ComponentType", "PersistentComponent",
]
