from __future__ import annotations

import re
from datetime import datetime, timezone

from noesis_agent.memory.memory_indexer import SENSITIVE_PATTERN
from noesis_agent.models.live import LiveEventIngestionResult, LiveEventType, LiveSessionEventRequest
from noesis_agent.models.runtime import AudienceSignal, SessionContext, SpeakerState
from noesis_agent.models.session import SessionState
from noesis_agent.models.transcript import SessionTranscriptEvent, TranscriptEvent, TranscriptEventType
from noesis_agent.services.host_decision_service import HostDecisionService
from noesis_agent.services.memory_service import MemoryService
from noesis_agent.services.response_mode_router import ResponseModeRouter
from noesis_agent.services.session_service import SessionService
from noesis_agent.services.topic_planning_service import TopicPlanningService
from noesis_agent.services.transcript_service import TranscriptService
from noesis_agent.utils.noesislogger import NoesisLogger


class LiveSessionService:
    """Ingests typed live events and updates session, room, transcript, memory, and host decisions."""

    def __init__(
        self,
        *,
        sessions: SessionService,
        transcripts: TranscriptService,
        memory: MemoryService,
        topics: TopicPlanningService,
        decisions: HostDecisionService,
        response_router: ResponseModeRouter,
    ) -> None:
        self.sessions = sessions
        self.transcripts = transcripts
        self.memory = memory
        self.topics = topics
        self.decisions = decisions
        self.response_router = response_router
        self.logger = NoesisLogger("noesis.service.live_session").logger

    def ingest_event(self, session_id: str, event: LiveSessionEventRequest) -> LiveEventIngestionResult:
        state = self.sessions.get_session(session_id)

        if event.event_type == LiveEventType.SESSION_STARTED and state.session.status != "live":
            state = self.sessions.start_session(session_id)

        transcript_event = self._transcript_event(session_id, event)
        memory_updated = False
        if transcript_event is not None:
            state = self.sessions.add_transcript_event(session_id, transcript_event)
            memory_updated = self._update_memory_if_safe(state, transcript_event)

        state = self._apply_event_to_room(state, event)

        if event.event_type == LiveEventType.SESSION_ENDED and state.session.status != "ended":
            state = self.sessions.save_state(state)
            state = self.sessions.end_session(session_id)
        else:
            state = self.sessions.save_state(state)

        context = self._build_context(state)
        decision = self.decisions.decide(context, event)
        route = self.response_router.route(context, decision)

        self.logger.info(
            "Live event ingested",
            extra={
                "session_id": session_id,
                "event_type": event.event_type.value,
                "intent": decision.intent.value,
                "response_mode": route.response_mode.value if route else None,
                "memory_updated": memory_updated,
            },
        )
        return LiveEventIngestionResult(
            session_state=state,
            decision=decision,
            response_route=route,
            transcript_event=transcript_event,
            memory_updated=memory_updated,
        )

    def _apply_event_to_room(self, state: SessionState, event: LiveSessionEventRequest) -> SessionState:
        now = datetime.now(timezone.utc)
        room = state.session.room_state

        if event.platform in {"x", "discord"}:
            room.platform = event.platform

        if event.audience_signal is not None:
            room.audience_signals.append(event.audience_signal)
            room.audience_signals = room.audience_signals[-20:]

        if event.event_type == LiveEventType.SPEAKER_JOINED:
            self._upsert_speaker(state, event.speaker or "unknown", event.role, active=True, seen_at=event.timestamp)
        elif event.event_type == LiveEventType.SPEAKER_LEFT:
            speaker = self._find_speaker(state, event.speaker)
            if speaker is not None:
                speaker.is_active = False
                speaker.last_seen_at = event.timestamp
        elif event.event_type == LiveEventType.INTERRUPTION:
            room.interruption_active = True
            speaker = self._find_speaker(state, event.speaker)
            if speaker is not None:
                speaker.interruption_count += 1
        elif event.event_type == LiveEventType.SILENCE_DETECTED:
            room.silence_seconds = event.silence_seconds
            room.energy_level = "low"
        elif event.event_type in {LiveEventType.USER_MESSAGE, LiveEventType.AUDIENCE_QUESTION, LiveEventType.HOST_MESSAGE}:
            room.silence_seconds = 0.0
            room.interruption_active = False
            if event.speaker:
                self._upsert_speaker(state, event.speaker, event.role, active=True, seen_at=event.timestamp)
        elif event.event_type == LiveEventType.MODERATION_SIGNAL:
            state.moderation_events.append(
                {
                    "event_id": event.event_id,
                    "speaker": event.speaker,
                    "content": event.content,
                    "timestamp": event.timestamp.isoformat(),
                }
            )
            room.energy_level = "chaotic"
            if event.audience_signal is None and event.content.strip():
                room.audience_signals.append(
                    AudienceSignal(
                        source=event.platform if event.platform in {"x", "discord"} else "api",
                        signal_type="moderation",
                        content=event.content,
                        weight=0.85,
                        source_user=event.speaker,
                    )
                )
        elif event.event_type == LiveEventType.TOPIC_CHANGE:
            topic_title = event.topic or event.content
            previous = room.active_topic
            self.topics.mark_active(state, topic_title)
            if previous and previous != topic_title:
                transition = self.topics.generate_transition(previous, topic_title)
                state.session.room_state.metadata["last_transition"] = transition
        elif event.event_type == LiveEventType.SESSION_STARTED:
            room.status = "live"
            room.metadata["started_event_at"] = now.isoformat()
        elif event.event_type == LiveEventType.SESSION_ENDED:
            room.status = "ending"
            room.metadata["ended_event_at"] = now.isoformat()

        if event.topic and event.event_type not in {LiveEventType.TOPIC_CHANGE}:
            self.topics.mark_active(state, event.topic)

        return state

    def _transcript_event(self, session_id: str, event: LiveSessionEventRequest) -> SessionTranscriptEvent | None:
        event_type = self._transcript_type(event)
        content = self._transcript_content(event)
        if event_type is None or not content:
            return None

        role = event.role
        speaker = event.speaker
        if event.event_type == LiveEventType.HOST_MESSAGE:
            role = "host"
            speaker = speaker or "NOESIS"
        elif event.event_type in {LiveEventType.SESSION_STARTED, LiveEventType.SESSION_ENDED, LiveEventType.SILENCE_DETECTED}:
            role = "system"
            speaker = speaker or "system"

        return SessionTranscriptEvent(
            event_id=event.event_id,
            session_id=session_id,
            speaker=speaker,
            role=role,
            event_type=event_type,
            content=content,
            timestamp=event.timestamp,
            platform=event.platform,
            metadata=event.metadata,
        )

    @staticmethod
    def _transcript_type(event: LiveSessionEventRequest) -> TranscriptEventType | None:
        mapping = {
            LiveEventType.USER_MESSAGE: TranscriptEventType.MESSAGE,
            LiveEventType.HOST_MESSAGE: TranscriptEventType.ANSWER,
            LiveEventType.AUDIENCE_QUESTION: TranscriptEventType.QUESTION,
            LiveEventType.INTERRUPTION: TranscriptEventType.MOD_ACTION,
            LiveEventType.MODERATION_SIGNAL: TranscriptEventType.MOD_ACTION,
            LiveEventType.TOPIC_CHANGE: TranscriptEventType.SYSTEM,
            LiveEventType.SESSION_STARTED: TranscriptEventType.SYSTEM,
            LiveEventType.SESSION_ENDED: TranscriptEventType.SYSTEM,
            LiveEventType.SILENCE_DETECTED: TranscriptEventType.SYSTEM,
        }
        return mapping.get(event.event_type)

    @staticmethod
    def _transcript_content(event: LiveSessionEventRequest) -> str:
        if event.content.strip():
            return event.content.strip()
        if event.event_type == LiveEventType.SESSION_STARTED:
            return "Session started."
        if event.event_type == LiveEventType.SESSION_ENDED:
            return "Session ended."
        if event.event_type == LiveEventType.SILENCE_DETECTED:
            return f"Silence detected for {event.silence_seconds:.1f} seconds."
        if event.event_type == LiveEventType.TOPIC_CHANGE and event.topic:
            return f"Topic changed to {event.topic}."
        return ""

    def _update_memory_if_safe(self, state: SessionState, event: TranscriptEvent) -> bool:
        if event.event_type not in {
            TranscriptEventType.MESSAGE,
            TranscriptEventType.QUESTION,
            TranscriptEventType.ANSWER,
        }:
            return False
        if not event.content.strip() or SENSITIVE_PATTERN.search(event.content):
            return False
        self.memory.index_transcript(state.session_id, f"{event.speaker or event.role}: {event.content}")
        return True

    def _build_context(self, state: SessionState) -> SessionContext:
        active_topic = state.session.room_state.active_topic or self._active_topic_title(state)
        memories = self.memory.semantic.search(active_topic or "general", limit=6)
        return SessionContext(
            session_id=state.session_id,
            title=state.title,
            mode=state.session.mode,
            room=state.session.room_state,
            topics=state.session.topic_plan,
            transcript_tail=self.transcripts.tail(state.transcript, limit=16),
            memory_refs=memories,
            action_items=self.transcripts.action_items(state.transcript),
        )

    @staticmethod
    def _active_topic_title(state: SessionState) -> str | None:
        if state.current_topic_index is not None and 0 <= state.current_topic_index < len(state.session.topic_plan):
            return state.session.topic_plan[state.current_topic_index].title
        active = next((topic.title for topic in state.session.topic_plan if topic.status == "active"), None)
        return active

    def _upsert_speaker(
        self,
        state: SessionState,
        display_name: str,
        role,
        *,
        active: bool,
        seen_at: datetime,
    ) -> SpeakerState:
        speaker = self._find_speaker(state, display_name)
        if speaker is None:
            speaker = SpeakerState(display_name=display_name, role=role, is_active=active, last_seen_at=seen_at)
            state.session.room_state.speakers.append(speaker)
        else:
            speaker.role = role
            speaker.is_active = active
            speaker.last_seen_at = seen_at
        return speaker

    @staticmethod
    def _find_speaker(state: SessionState, display_name: str | None) -> SpeakerState | None:
        if not display_name:
            return None
        normalized = display_name.strip().lower()
        return next(
            (speaker for speaker in state.session.room_state.speakers if speaker.display_name.lower() == normalized),
            None,
        )


__all__ = ["LiveSessionService"]
