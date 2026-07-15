from __future__ import annotations

import asyncio

from noesis_agent.application.intelligence.ports import (
    IdempotencyPort,
    ModelPort,
    ModerationPort,
    RetrievalPort,
)
from noesis_agent.domain.contracts.intelligence import (
    DirectResponse,
    IntelligenceRequest,
    IntelligenceResult,
    ModerationAction,
    ModerationDirection,
    Refusal,
    ToolCall,
)
from noesis_agent.cognition.tools import ToolRegistry


class IntelligencePipeline:
    """One bounded path for moderation, retrieval, cognition, tools, and persistence."""

    def __init__(
        self,
        *,
        moderation: ModerationPort,
        retrieval: RetrievalPort,
        model: ModelPort,
        idempotency: IdempotencyPort,
        tools: ToolRegistry,
        deadline_seconds: float = 45.0,
    ) -> None:
        self._moderation = moderation
        self._retrieval = retrieval
        self._model = model
        self._idempotency = idempotency
        self._tools = tools
        self._deadline_seconds = deadline_seconds

    async def process(self, request: IntelligenceRequest) -> IntelligenceResult:
        return await asyncio.wait_for(
            self._process(request), timeout=self._deadline_seconds
        )

    async def _process(self, request: IntelligenceRequest) -> IntelligenceResult:
        claimed = await self._idempotency.claim(
            request.tenant_id, request.event_id, ttl_seconds=3600
        )
        inbound = await self._moderation.evaluate(
            tenant_id=request.tenant_id,
            text=request.text,
            direction=ModerationDirection.INBOUND,
        )
        if not claimed:
            return IntelligenceResult(
                event_id=request.event_id,
                correlation_id=request.correlation_id,
                outcome=Refusal(reason="Duplicate event."),
                provider="none",
                inbound_moderation=inbound,
                degraded_capabilities=["duplicate_event"],
            )
        if inbound.action in {ModerationAction.BLOCK, ModerationAction.ESCALATE}:
            return IntelligenceResult(
                event_id=request.event_id,
                correlation_id=request.correlation_id,
                outcome=Refusal(
                    reason="The request was blocked by inbound safety policy."
                ),
                provider="safety",
                inbound_moderation=inbound,
            )

        context = await self._retrieval.retrieve(request, limit=6)
        outcome, provider, used_fallback = await self._model.generate(request, context)
        if isinstance(outcome, ToolCall):
            tool_result = await self._tools.execute(
                outcome,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                authorized_capabilities=request.authorized_capabilities,
            )
            outcome = DirectResponse(text=tool_result)

        output_text = self._outcome_text(outcome)
        outbound = await self._moderation.evaluate(
            tenant_id=request.tenant_id,
            text=output_text,
            direction=ModerationDirection.OUTBOUND,
        )
        if outbound.action in {ModerationAction.BLOCK, ModerationAction.ESCALATE}:
            outcome = Refusal(
                reason="The generated response was withheld by outbound safety policy."
            )
        else:
            await self._retrieval.remember(request, output_text)

        degraded = [
            item.name
            for item in (
                *self._model.health(),
                self._retrieval.health(),
                self._moderation.health(),
                self._idempotency.health(),
            )
            if item.state.value not in {"ready", "disabled"}
        ]
        return IntelligenceResult(
            event_id=request.event_id,
            correlation_id=request.correlation_id,
            outcome=outcome,
            provider=provider,
            used_fallback=used_fallback,
            retrieved=context,
            inbound_moderation=inbound,
            outbound_moderation=outbound,
            degraded_capabilities=degraded,
        )

    @staticmethod
    def _outcome_text(outcome: object) -> str:
        if isinstance(outcome, DirectResponse):
            return outcome.text
        if hasattr(outcome, "question"):
            return str(getattr(outcome, "question"))
        return str(getattr(outcome, "reason", "Unable to provide a response."))
