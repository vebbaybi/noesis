from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from noesis_agent.interfaces.api.app import app
from noesis_agent.infrastructure.config.settings import settings
from noesis_agent.domain.contracts.live import LiveEventType, LiveSessionEventRequest
from noesis_agent.domain.contracts.runtime import HostIntent, ResponseMode, RoomState, SessionContext, SpeakerState, TopicPlan
from noesis_agent.domain.contracts.session import SessionCreateRequest
from noesis_agent.domain.entities.transcript import TranscriptEvent
from noesis_agent.runtime.container import get_container
from noesis_agent.application.conversation.host_decisions import HostDecisionService
from noesis_agent.capabilities.media.post_show_service import PostShowArtifactService
from noesis_agent.application.conversation.response_modes import ResponseModeRouter
from noesis_agent.application.conversation.sessions import SessionService
from noesis_agent.capabilities.content.summary_service import SummaryService
from noesis_agent.capabilities.scheduling.topic_planning_service import TopicPlanningService
from noesis_agent.application.conversation.transcripts import TranscriptService
from noesis_agent.infrastructure.persistence.json_store import JsonStore


class DisabledOpenAI:
    def is_enabled(self) -> bool:
        return False


def _context(*, silence_seconds: float = 0.0, mode: str = "cohost") -> SessionContext:
    return SessionContext(
        session_id="session-1",
        title="Live Test",
        mode=mode,
        room=RoomState(
            platform="discord",
            status="live",
            active_topic="NFT liquidity",
            silence_seconds=silence_seconds,
            speakers=[SpeakerState(display_name="Alice", role="guest", is_active=True)],
        ),
        topics=[TopicPlan(title="NFT liquidity", status="active")],
        transcript_tail=[
            TranscriptEvent(session_id="session-1", speaker="Alice", content="Can you explain the liquidity risk?"),
        ],
    )


def test_host_decision_classifies_live_intents() -> None:
    service = HostDecisionService(silence_threshold_seconds=5)
    context = _context()

    question = service.decide(
        context,
        LiveSessionEventRequest(
            event_type=LiveEventType.AUDIENCE_QUESTION,
            speaker="Alice",
            content="Can you explain the liquidity risk?",
        ),
    )
    assert question.intent == HostIntent.ANSWER_DIRECTLY

    silence = service.decide(
        _context(silence_seconds=9),
        LiveSessionEventRequest(event_type=LiveEventType.SILENCE_DETECTED, silence_seconds=9),
    )
    assert silence.intent == HostIntent.RECOVER_SILENCE

    moderation = service.decide(
        context,
        LiveSessionEventRequest(event_type=LiveEventType.MODERATION_SIGNAL, speaker="Bob", content="That is a scam."),
    )
    assert moderation.intent == HostIntent.MODERATE_CONFLICT

    closing = service.decide(
        context,
        LiveSessionEventRequest(event_type=LiveEventType.USER_MESSAGE, speaker="Host", content="Let's wrap up."),
    )
    assert closing.intent == HostIntent.CLOSE_SESSION


def test_response_mode_router_builds_cognition_request() -> None:
    context = _context()
    decision = HostDecisionService().decide(
        context,
        LiveSessionEventRequest(
            event_type=LiveEventType.AUDIENCE_QUESTION,
            speaker="Alice",
            content="Why is liquidity risk different from floor price risk?",
        ),
    )

    route = ResponseModeRouter(TranscriptService()).route(context, decision)

    assert route is not None
    assert route.response_mode in {ResponseMode.DEEP_ANSWER, ResponseMode.COHOST_REPLY}
    assert route.cognition_request.session_id == "session-1"
    assert route.cognition_request.intent == HostIntent.ANSWER_DIRECTLY


def test_topic_queue_behavior(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    state = SessionService(store).create_session(SessionCreateRequest(plan_id="plan-1", platform="discord"))
    topics = TopicPlanningService()

    state.session.topic_plan = topics.create_topic_queue(["Opening", "Market risk"])
    active = topics.mark_active(state, "Opening")
    assert active.status == "active"
    assert state.session.room_state.active_topic == "Opening"

    parked = topics.park_topic(state, "Opening")
    assert parked is not None
    assert parked.status == "parked"

    resumed = topics.resume_parked_topic(state, "Opening")
    assert resumed.status == "active"

    completed = topics.mark_completed(state, "Opening")
    assert completed is not None
    assert completed.status == "done"

    fallback = topics.suggest_fallback_topic(state)
    assert fallback.title
    assert topics.generate_transition("Opening", "Market risk").startswith("Let's park")


def test_live_event_ingestion_updates_transcript_room_and_memory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "enable_x", False)
    monkeypatch.setattr(settings, "enable_discord", False)
    get_container.cache_clear()

    container = get_container()
    state = container.sessions.create_session(
        SessionCreateRequest(plan_id="plan-1", title="Daily Live Test", platform="discord", mode="cohost")
    )
    container.topic_planning.add_topic(state, "NFT liquidity")
    container.sessions.save_state(state)
    container.sessions.start_session(state.session_id)

    result = container.live_sessions.ingest_event(
        state.session_id,
        LiveSessionEventRequest(
            event_type=LiveEventType.AUDIENCE_QUESTION,
            speaker="Alice",
            role="guest",
            topic="NFT liquidity",
            content="What liquidity risk should collectors watch?",
            platform="discord",
        ),
    )

    assert result.transcript_event is not None
    assert result.decision.intent == HostIntent.ANSWER_DIRECTLY
    assert result.response_route is not None
    assert result.session_state.last_speaker == "Alice"
    assert result.memory_updated is True
    assert container.memory.semantic.search("liquidity")

    secret_result = container.live_sessions.ingest_event(
        state.session_id,
        LiveSessionEventRequest(
            event_type=LiveEventType.USER_MESSAGE,
            speaker="Alice",
            content="api token secret should not be remembered",
        ),
    )
    assert secret_result.memory_updated is False
    assert not any("api token" in hit for hit in container.memory.semantic.search("general", limit=20))

    get_container.cache_clear()


def test_post_show_artifacts_have_deterministic_fallback(tmp_path: Path) -> None:
    transcript_service = TranscriptService()
    sessions = SessionService(JsonStore(tmp_path), transcript_service)
    state = sessions.create_session(SessionCreateRequest(plan_id="plan-1", title="Fallback Show", platform="discord"))
    sessions.start_session(state.session_id)
    state = sessions.add_transcript_event(
        state.session_id,
        transcript_service.normalize_event(
            state.session_id,
            TranscriptEvent(
                session_id=state.session_id,
                speaker="Alice",
                content="What is the risk if liquidity fades?",
                event_type="question",
            ),
        ),
    )
    topics = TopicPlanningService()
    topics.add_topic(state, "Liquidity risk")

    artifacts = asyncio.run(
        PostShowArtifactService(SummaryService(DisabledOpenAI()), transcript_service).generate(state)
    )

    assert artifacts.summary.headline == "Fallback Show recap"
    assert artifacts.highlights
    assert artifacts.topics == ["Liquidity risk"]
    assert artifacts.notable_audience_questions


def test_api_live_session_flow(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "enable_x", False)
    monkeypatch.setattr(settings, "enable_discord", False)
    get_container.cache_clear()

    with TestClient(app) as client:
        create = client.post("/sessions", json={"plan_id": "plan-api", "title": "API Live", "platform": "discord"})
        assert create.status_code == 200
        session_id = create.json()["session_id"]

        start = client.post(f"/sessions/{session_id}/start")
        assert start.status_code == 200

        event = client.post(
            f"/sessions/{session_id}/events",
            json={
                "event_type": "audience_question",
                "speaker": "Alice",
                "role": "guest",
                "content": "What should we watch next?",
                "platform": "discord",
            },
        )
        assert event.status_code == 200
        assert event.json()["decision"]["intent"] == "answer_directly"

        active = client.get("/sessions", params={"active_only": True})
        assert active.status_code == 200
        assert any(item["session_id"] == session_id for item in active.json())

        artifacts = client.get(f"/sessions/{session_id}/artifacts")
        assert artifacts.status_code == 200
        assert artifacts.json()["session_id"] == session_id

    get_container.cache_clear()
