from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from noesis_agent.domain.contracts.intelligence import (
    CapabilityHealth,
    IntelligenceRequest,
    ModerationDecision,
    ModerationDirection,
    RetrievalItem,
    StructuredOutcome,
)


class ModerationPort(Protocol):
    async def evaluate(self, *, tenant_id: str, text: str, direction: ModerationDirection) -> ModerationDecision: ...
    def health(self) -> CapabilityHealth: ...


class RetrievalPort(Protocol):
    async def retrieve(self, request: IntelligenceRequest, *, limit: int) -> list[RetrievalItem]: ...
    async def remember(self, request: IntelligenceRequest, text: str) -> None: ...
    def health(self) -> CapabilityHealth: ...


class ModelPort(Protocol):
    async def generate(self, request: IntelligenceRequest, context: Sequence[RetrievalItem]) -> tuple[StructuredOutcome, str, bool]: ...
    def health(self) -> list[CapabilityHealth]: ...


class IdempotencyPort(Protocol):
    async def claim(self, tenant_id: str, event_id: str, *, ttl_seconds: int) -> bool: ...
    def health(self) -> CapabilityHealth: ...
