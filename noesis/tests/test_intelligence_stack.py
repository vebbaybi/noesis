from __future__ import annotations

from pydantic import BaseModel
import pytest

from noesis_agent.application.intelligence.pipeline import IntelligencePipeline
from noesis_agent.capabilities.moderation.pipeline import LexicalModerator, TwoStageModeration
from noesis_agent.cognition.tools import SideEffect, ToolDefinition, ToolRegistry
from noesis_agent.domain.contracts.intelligence import (
    CapabilityHealth, CapabilityState, DirectResponse, IntelligenceRequest,
    ModerationAction, ModerationDirection, RetrievalItem, ToolCall,
)
from noesis_agent.infrastructure.coordination.idempotency import LocalIdempotencyStore


class _Retrieval:
    def __init__(self) -> None:
        self.remembered: list[tuple[str, str]] = []

    async def retrieve(self, request: IntelligenceRequest, *, limit: int) -> list[RetrievalItem]:
        return [RetrievalItem(point_id="p1", tenant_id=request.tenant_id, text="tenant context",
                              score=0.8, source_id="s1", provenance="test")]

    async def remember(self, request: IntelligenceRequest, text: str) -> None:
        self.remembered.append((request.tenant_id, text))

    def health(self) -> CapabilityHealth:
        return CapabilityHealth(name="rag", state=CapabilityState.READY)


class _Model:
    async def generate(self, request: IntelligenceRequest,
                       context: list[RetrievalItem]) -> tuple[DirectResponse, str, bool]:
        assert all(item.tenant_id == request.tenant_id for item in context)
        return DirectResponse(text="safe response"), "local-test", False

    def health(self) -> list[CapabilityHealth]:
        return [CapabilityHealth(name="llm:local", state=CapabilityState.READY)]


def _request(event_id: str = "event-1") -> IntelligenceRequest:
    return IntelligenceRequest(event_id=event_id, tenant_id="tenant-a", user_id="user-a",
                               conversation_id="conversation-a", text="Explain the result")


def test_lexical_normalization_detects_evasion_without_changing_original() -> None:
    original = "k.i.l.l"
    categories, evidence = LexicalModerator().classify(original)
    assert original == "k.i.l.l"
    assert categories == ["credible_violence"]
    assert evidence


@pytest.mark.asyncio
async def test_pipeline_runs_both_moderation_directions_and_persists() -> None:
    retrieval = _Retrieval()
    pipeline = IntelligencePipeline(
        moderation=TwoStageModeration(), retrieval=retrieval, model=_Model(),
        idempotency=LocalIdempotencyStore(), tools=ToolRegistry(),
    )
    result = await pipeline.process(_request())
    assert result.provider == "local-test"
    assert result.inbound_moderation.direction is ModerationDirection.INBOUND
    assert result.outbound_moderation is not None
    assert result.outbound_moderation.direction is ModerationDirection.OUTBOUND
    assert retrieval.remembered == [("tenant-a", "safe response")]


@pytest.mark.asyncio
async def test_pipeline_rejects_duplicate_event() -> None:
    store = LocalIdempotencyStore()
    pipeline = IntelligencePipeline(moderation=TwoStageModeration(), retrieval=_Retrieval(),
                                    model=_Model(), idempotency=store, tools=ToolRegistry())
    await pipeline.process(_request())
    duplicate = await pipeline.process(_request())
    assert duplicate.provider == "none"
    assert "duplicate_event" in duplicate.degraded_capabilities


@pytest.mark.asyncio
async def test_inbound_moderation_blocks_before_generation() -> None:
    pipeline = IntelligencePipeline(moderation=TwoStageModeration(), retrieval=_Retrieval(),
                                    model=_Model(), idempotency=LocalIdempotencyStore(), tools=ToolRegistry())
    result = await pipeline.process(_request().model_copy(update={"text": "I will k.i.l.l them"}))
    assert result.inbound_moderation.action is ModerationAction.BLOCK
    assert result.provider == "safety"


class _Args(BaseModel):
    value: int


class _Result(BaseModel):
    doubled: int


@pytest.mark.asyncio
async def test_tool_registry_validates_authorization_and_arguments() -> None:
    async def handler(arguments: _Args, tenant_id: str, user_id: str) -> _Result:
        assert tenant_id == "tenant-a" and user_id == "user-a"
        return _Result(doubled=arguments.value * 2)

    registry = ToolRegistry()
    registry.register(ToolDefinition(
        tool_id="math.double", purpose="Double an integer", arguments_model=_Args,
        result_model=_Result, required_capability="math", side_effect=SideEffect.NONE,
        timeout_seconds=1.0, handler=handler,
    ))
    with pytest.raises(PermissionError):
        await registry.execute(ToolCall(tool_id="math.double", arguments={"value": 2}),
                               tenant_id="tenant-a", user_id="user-a", authorized_capabilities=frozenset())
    result = await registry.execute(ToolCall(tool_id="math.double", arguments={"value": 2}),
                                    tenant_id="tenant-a", user_id="user-a",
                                    authorized_capabilities=frozenset({"math"}))
    assert result == '{"doubled":4}'
