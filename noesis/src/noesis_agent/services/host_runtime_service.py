from __future__ import annotations

from noesis_agent.cognition.providers import CognitionProviderRouter
from noesis_agent.models.cognition import CognitionResponse, ResponseRoute
from noesis_agent.models.live import (
    HostOutput,
    HostTurnRequest,
    HostTurnResult,
    LiveEventIngestionResult,
    OutputDispatchResult,
)
from noesis_agent.models.transcript import SessionTranscriptEvent, TranscriptEventType
from noesis_agent.services.live_session_service import LiveSessionService
from noesis_agent.services.memory_service import MemoryService
from noesis_agent.services.output_router import OutputRouter
from noesis_agent.services.session_service import SessionService
from noesis_agent.services.transcript_service import TranscriptService
from noesis_agent.utils.noesislogger import NoesisLogger


class HostRuntimeService:
    """Executes a complete live host turn from event ingestion through output dispatch."""

    def __init__(
        self,
        *,
        live_sessions: LiveSessionService,
        cognition: CognitionProviderRouter,
        sessions: SessionService,
        transcripts: TranscriptService,
        memory: MemoryService,
        output_router: OutputRouter,
    ) -> None:
        self.live_sessions = live_sessions
        self.cognition = cognition
        self.sessions = sessions
        self.transcripts = transcripts
        self.memory = memory
        self.output_router = output_router
        self.logger = NoesisLogger("noesis.service.host_runtime").logger

    async def execute_turn(self, session_id: str, request: HostTurnRequest) -> HostTurnResult:
        ingestion = self.live_sessions.ingest_event(session_id, request.event)
        route = ingestion.response_route
        warnings: list[str] = []
        errors: list[str] = []

        if not request.generate_response:
            warnings.append("Host response generation was disabled for this turn.")
            return self._empty_result(session_id, request, ingestion, warnings=warnings, errors=errors)

        if route is None or not route.should_generate:
            warnings.append("The host decision did not require a generated response.")
            return self._empty_result(session_id, request, ingestion, warnings=warnings, errors=errors)

        cognition_response = await self._generate_response(route, request, warnings, errors)
        host_text = cognition_response.text.strip()
        if not host_text:
            errors.append("Cognition provider returned an empty host response.")
            if not request.allow_deterministic_fallback:
                return self._empty_result(session_id, request, ingestion, warnings=warnings, errors=errors)
            host_text = self._deterministic_fallback(route)
            cognition_response = cognition_response.model_copy(
                update={"provider_name": "deterministic-fallback", "text": host_text, "used_fallback": True}
            )
            warnings.append("Empty cognition response replaced with deterministic fallback text.")

        host_event = SessionTranscriptEvent(
            session_id=session_id,
            speaker="NOESIS",
            role="host",
            event_type=TranscriptEventType.ANSWER,
            content=host_text,
            platform=request.event.platform,
            metadata={
                "source_event_id": request.event.event_id,
                "host_intent": route.decision.intent.value,
                "response_mode": route.response_mode.value,
                "cognition_provider": cognition_response.provider_name,
                "used_fallback": cognition_response.used_fallback,
            },
        )
        state = self.sessions.add_transcript_event(session_id, host_event)
        normalized_host_event = state.transcript[-1] if state.transcript else None

        memory_write_ids = self.memory.remember_if_safe(session_id, speaker="NOESIS", text=host_text)
        output = HostOutput(
            session_id=session_id,
            text=host_text,
            channels=request.output_channels or self.output_router.select_channels(state),
            response_mode=route.response_mode,
            host_intent=route.decision.intent,
            metadata={
                "source_event_id": request.event.event_id,
                "topic": route.decision.topic or state.session.room_state.active_topic,
                "transcript_event_id": normalized_host_event.event_id if normalized_host_event else None,
            },
        )
        dispatch_results = await self.output_router.dispatch(output, state)
        final_ingestion = ingestion.model_copy(update={"session_state": state})

        self.logger.info(
            "Host turn completed",
            extra={
                "session_id": session_id,
                "event_id": request.event.event_id,
                "intent": route.decision.intent.value,
                "response_mode": route.response_mode.value,
                "provider": cognition_response.provider_name,
                "dispatch_statuses": [result.status.value for result in dispatch_results],
            },
        )

        return HostTurnResult(
            session_id=session_id,
            ingested_event_id=request.event.event_id,
            host_intent=route.decision.intent,
            response_mode=route.response_mode,
            cognition_provider_used=cognition_response.provider_name,
            host_text=host_text,
            transcript_event_id=normalized_host_event.event_id if normalized_host_event else None,
            memory_write_ids=memory_write_ids,
            dispatch_results=dispatch_results,
            warnings=warnings,
            errors=errors,
            ingestion=final_ingestion,
        )

    async def _generate_response(
        self,
        route: ResponseRoute,
        request: HostTurnRequest,
        warnings: list[str],
        errors: list[str],
    ) -> CognitionResponse:
        try:
            return await self.cognition.generate(route.cognition_request)
        except Exception as exc:
            self.logger.error(
                "Cognition execution failed during host turn",
                exc_info=exc,
                extra={
                    "session_id": route.cognition_request.session_id,
                    "request_id": route.cognition_request.request_id,
                },
            )
            errors.append(f"Cognition provider failed: {exc}")
            if not request.allow_deterministic_fallback:
                return CognitionResponse(
                    request_id=route.cognition_request.request_id,
                    provider_name="unavailable",
                    text="",
                    confidence=0.0,
                    used_fallback=False,
                )
            warnings.append("Cognition provider failed; deterministic host fallback was used.")
            return CognitionResponse(
                request_id=route.cognition_request.request_id,
                provider_name="deterministic-fallback",
                text=self._deterministic_fallback(route),
                confidence=0.35,
                used_fallback=True,
                metadata={"fallback_reason": str(exc)},
            )

    def _empty_result(
        self,
        session_id: str,
        request: HostTurnRequest,
        ingestion: LiveEventIngestionResult,
        *,
        warnings: list[str],
        errors: list[str],
    ) -> HostTurnResult:
        response_mode = ingestion.response_route.response_mode if ingestion.response_route else None
        return HostTurnResult(
            session_id=session_id,
            ingested_event_id=request.event.event_id,
            host_intent=ingestion.decision.intent,
            response_mode=response_mode,
            host_text="",
            dispatch_results=[],
            warnings=warnings,
            errors=errors,
            ingestion=ingestion,
        )

    @staticmethod
    def _deterministic_fallback(route: ResponseRoute) -> str:
        fallback = route.cognition_request.local_fallback.strip()
        if fallback:
            return fallback
        topic = route.decision.topic or "this thread"
        return (
            f"I hit a cognition provider error, so here is the safe fallback: on {topic}, "
            "answer the concrete question first, keep certainty scoped, and move the room to the next useful step."
        )


__all__ = ["HostRuntimeService"]
