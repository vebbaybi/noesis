from __future__ import annotations

from pathlib import Path

from noesis_agent.domain.contracts.session import SessionCreateRequest
from noesis_agent.domain.entities.transcript import SessionTranscriptEvent
from noesis_agent.memory.service import MemoryService
from noesis_agent.application.conversation.sessions import SessionService
from noesis_agent.application.conversation.transcripts import TranscriptService
from noesis_agent.infrastructure.persistence.json_store import JsonStore


def test_session_service_tracks_mode_room_state_and_speakers(tmp_path: Path) -> None:
    service = SessionService(JsonStore(tmp_path), TranscriptService())
    state = service.create_session(
        SessionCreateRequest(plan_id="plan-1", title="Solo Host Test", platform="discord", mode="solo")
    )

    assert state.session.mode == "solo"
    live = service.start_session(state.session_id)
    assert live.status == "live"
    assert live.session.room_state.status == "live"

    updated = service.add_transcript_event(
        state.session_id,
        SessionTranscriptEvent(speaker="Alice", role="guest", text="Action: pull the floor price before the recap."),
    )

    assert updated.last_speaker == "Alice"
    assert updated.session.room_state.speakers[0].display_name == "Alice"
    assert updated.session.room_state.speakers[0].role == "guest"


def test_transcript_service_renders_counts_and_action_items() -> None:
    service = TranscriptService()
    event = service.normalize_event(
        "session-1",
        SessionTranscriptEvent(speaker="Host", role="host", text="Follow up: send the guest notes."),
    )

    assert event.session_id == "session-1"
    assert service.render_text([event]) == "Host: Follow up: send the guest notes."
    assert service.speaker_counts([event]) == {"Host": 1}
    assert service.action_items([event])[0].description == "send the guest notes."


def test_memory_service_indexes_structured_non_sensitive_facts(tmp_path: Path) -> None:
    memory = MemoryService(tmp_path)
    memory.index_transcript(
        "session-1",
        "host: NFT liquidity needs downside framing.\n"
        "guest: API token secret should never be stored.\n",
    )

    hits = memory.semantic.search("liquidity")
    assert any("downside framing" in hit for hit in hits)
    assert not any("token secret" in hit for hit in memory.semantic.search("general", limit=10))

    records = memory.semantic.search_records("liquidity")
    assert records
    assert records[0].confidence > 0
    assert "session:session-1" in records[0].source_tags
