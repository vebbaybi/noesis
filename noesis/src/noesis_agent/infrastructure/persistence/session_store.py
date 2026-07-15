from __future__ import annotations

from pathlib import Path
from typing import Iterable

from noesis_agent.domain.contracts.session import Session, SessionState
from noesis_agent.domain.entities.transcript import TranscriptEvent
from noesis_agent.infrastructure.persistence.json_store import JsonStore


class SessionStore:
    """Persists sessions and transcript state on disk via JsonStore."""

    def __init__(self, data_dir: Path) -> None:
        self.store = JsonStore(data_dir / "sessions")
        self.transcripts = JsonStore(data_dir / "transcripts")

    def save_session(self, session: Session, state: SessionState | None = None) -> None:
        self.store.write("sessions", session.session_id, session.model_dump(mode="json"))
        if state:
            self.save_state(state)

    def save_state(self, state: SessionState) -> None:
        self.store.write("session_states", state.session.session_id, state.model_dump(mode="json"))

    def load_state(self, session_id: str) -> SessionState | None:
        data = self.store.read("session_states", session_id)
        return SessionState(**data) if data else None

    def append_transcript(self, session_id: str, events: Iterable[TranscriptEvent]) -> None:
        for event in events:
            self.transcripts.write(
                "events",
                f"{session_id}:{event.event_id}",
                event.model_dump(mode="json", exclude={"text"}),
            )

    def list_transcript(self, session_id: str) -> list[TranscriptEvent]:
        all_events = self.transcripts.list("events")
        filtered = [e for e in all_events if str(e.get("session_id")) == session_id]
        return [TranscriptEvent(**e) for e in filtered]
