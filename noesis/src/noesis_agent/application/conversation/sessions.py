from __future__ import annotations

from datetime import datetime, timezone

from noesis_agent.domain.contracts.session import (
    Session,
    SessionCreateRequest,
    SessionPlatformState,
    SessionState,
)
from noesis_agent.domain.entities.transcript import SessionTranscriptEvent
from noesis_agent.domain.contracts.runtime import SpeakerState
from noesis_agent.application.conversation.transcripts import TranscriptService
from noesis_agent.application.ports import DocumentStore


class SessionService:
    def __init__(self, store: DocumentStore, transcript_service: TranscriptService | None = None) -> None:
        self.store = store
        self.transcript_service = transcript_service or TranscriptService()

    def _serialize_state(self, state: SessionState) -> dict:
        payload = state.model_dump(mode="json")
        payload.pop("session_id", None)
        payload.pop("status", None)
        payload.pop("title", None)

        transcript_payload = payload.get("transcript")
        if isinstance(transcript_payload, list):
            for item in transcript_payload:
                if isinstance(item, dict):
                    item.pop("text", None)

        session_payload = payload.get("session")
        if isinstance(session_payload, dict):
            session_payload.pop("primary_platform", None)
        return payload

    def create_session(self, payload: SessionCreateRequest) -> SessionState:
        title = payload.title or f"NOESIS Session {payload.plan_id[:8]}"
        platforms = [SessionPlatformState(platform=platform) for platform in payload.platforms]
        session = Session(
            plan_id=payload.plan_id,
            title=title,
            mode=payload.mode,
            platforms=platforms,
            status="scheduled" if payload.scheduled_start else "created",
            hosts=payload.hosts,
            guests=payload.guests,
        )
        state = SessionState(session=session)
        self.store.write(
            "sessions",
            session.session_id,
            self._serialize_state(state),
        )
        return state

    def save_state(self, state: SessionState) -> SessionState:
        state.session.updated_at = datetime.now(timezone.utc)
        self.store.write(
            "sessions",
            state.session.session_id,
            self._serialize_state(state),
        )
        return state

    def get_session(self, session_id: str) -> SessionState:
        data = self.store.read("sessions", session_id)
        if not data:
            raise KeyError(f"Session not found: {session_id}")
        return SessionState.model_validate(data)

    def list_sessions(self, *, active_only: bool = False) -> list[SessionState]:
        sessions = [SessionState.model_validate(data) for data in self.store.list("sessions")]
        if active_only:
            sessions = [
                state
                for state in sessions
                if state.session.status in {"created", "scheduled", "live"}
            ]
        return sorted(sessions, key=lambda state: state.session.updated_at, reverse=True)

    def start_session(self, session_id: str) -> SessionState:
        state = self.get_session(session_id)
        if state.session.status == "ended":
            raise ValueError(f"Cannot restart ended session: {session_id}")
        now = datetime.now(timezone.utc)
        state.session.status = "live"
        state.session.started_at = now
        state.session.updated_at = now
        state.session.room_state.status = "live"
        state.session.room_state.platform = state.session.primary_platform if state.session.primary_platform in {"x", "discord"} else "unknown"
        for platform_state in state.session.platforms:
            platform_state.status = "live"
            platform_state.started_at = now
            platform_state.last_heartbeat = now
        return self.save_state(state)

    def end_session(self, session_id: str) -> SessionState:
        state = self.get_session(session_id)
        now = datetime.now(timezone.utc)
        state.session.status = "ended"
        state.session.ended_at = now
        state.session.updated_at = now
        state.session.room_state.status = "ended"
        if state.session.started_at:
            state.session.duration_seconds = int((now - state.session.started_at).total_seconds())
        for platform_state in state.session.platforms:
            platform_state.status = "ended"
            platform_state.ended_at = now
            platform_state.last_heartbeat = now
        return self.save_state(state)

    def add_transcript_event(self, session_id: str, event: SessionTranscriptEvent) -> SessionState:
        state = self.get_session(session_id)
        normalized_event = self.transcript_service.normalize_event(session_id, event)
        state.transcript.append(normalized_event)
        if normalized_event.speaker:
            state.last_speaker = normalized_event.speaker
            state.active_speakers = [speaker for speaker in state.active_speakers if speaker != normalized_event.speaker]
            state.active_speakers.append(normalized_event.speaker)
            state.active_speakers = state.active_speakers[-6:]
            existing_speaker = next(
                (
                    speaker
                    for speaker in state.session.room_state.speakers
                    if speaker.display_name == normalized_event.speaker
                ),
                None,
            )
            if existing_speaker is None:
                state.session.room_state.speakers.append(
                    SpeakerState(
                        display_name=normalized_event.speaker,
                        role=normalized_event.role,
                        is_active=True,
                    )
                )
            else:
                existing_speaker.is_active = True
                existing_speaker.last_seen_at = datetime.now(timezone.utc)
        state.session.updated_at = datetime.now(timezone.utc)
        return self.save_state(state)
