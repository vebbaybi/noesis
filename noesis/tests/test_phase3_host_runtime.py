from __future__ import annotations

import asyncio
from dataclasses import dataclass

from fastapi.testclient import TestClient

from noesis_agent.api.app import app
from noesis_agent.config.settings import settings
from noesis_agent.models.cognition import CognitionRequest, CognitionResponse
from noesis_agent.models.live import (
    HostOutput,
    HostTurnRequest,
    LiveEventType,
    LiveSessionEventRequest,
    OutputChannel,
    OutputStatus,
)
from noesis_agent.models.session import SessionCreateRequest
from noesis_agent.services.container import get_container
from noesis_agent.services.host_runtime_service import HostRuntimeService
from noesis_agent.services.output_adapters import DiscordOutputAdapter, LocalTextOutputAdapter
from noesis_agent.services.output_router import OutputRouter


def _disable_external_integrations(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "discord_bot_token", "")
    monkeypatch.setattr(settings, "enable_discord", False)
    monkeypatch.setattr(settings, "enable_x", False)
    monkeypatch.setattr(settings, "x_api_key", "")
    monkeypatch.setattr(settings, "x_api_secret", "")
    monkeypatch.setattr(settings, "x_access_token", "")
    monkeypatch.setattr(settings, "x_access_token_secret", "")
    monkeypatch.setattr(settings, "x_bearer_token", "")
    get_container.cache_clear()


def _live_session(container, *, title: str = "Phase 3 Live"):
    state = container.sessions.create_session(
        SessionCreateRequest(plan_id="phase-3", title=title, platform="discord", mode="cohost")
    )
    container.topic_planning.add_topic(state, "Collector safety")
    container.sessions.save_state(state)
    return container.sessions.start_session(state.session_id)


def test_full_host_turn_generates_transcript_memory_and_local_output(tmp_path, monkeypatch) -> None:
    _disable_external_integrations(tmp_path, monkeypatch)
    container = get_container()
    state = _live_session(container)

    result = asyncio.run(
        container.host_runtime.execute_turn(
            state.session_id,
            HostTurnRequest(
                event=LiveSessionEventRequest(
                    event_type=LiveEventType.AUDIENCE_QUESTION,
                    speaker="Alice",
                    role="guest",
                    content="How should collectors evaluate wallet-drain risk?",
                    platform="discord",
                    topic="Collector safety",
                ),
                output_channels=[OutputChannel.LOCAL_TEXT],
            ),
        )
    )

    assert result.host_text
    assert result.cognition_provider_used == "local-fallback"
    assert result.transcript_event_id
    assert result.memory_write_ids
    assert result.dispatch_results[0].channel == OutputChannel.LOCAL_TEXT
    assert result.dispatch_results[0].status == OutputStatus.SENT

    saved = container.sessions.get_session(state.session_id)
    assert len(saved.transcript) == 2
    assert saved.transcript[-1].speaker == "NOESIS"
    assert saved.transcript[-1].metadata["source_event_id"] == result.ingested_event_id
    get_container.cache_clear()


def test_host_runtime_uses_deterministic_fallback_when_provider_fails(tmp_path, monkeypatch) -> None:
    _disable_external_integrations(tmp_path, monkeypatch)
    container = get_container()
    state = _live_session(container, title="Provider Failure")

    class FailingCognition:
        async def generate(self, request: CognitionRequest) -> CognitionResponse:
            raise RuntimeError(f"provider unavailable for {request.request_id}")

    runtime = HostRuntimeService(
        live_sessions=container.live_sessions,
        cognition=FailingCognition(),
        sessions=container.sessions,
        transcripts=container.transcripts,
        memory=container.memory,
        output_router=container.output_router,
    )

    result = asyncio.run(
        runtime.execute_turn(
            state.session_id,
            HostTurnRequest(
                event=LiveSessionEventRequest(
                    event_type=LiveEventType.USER_MESSAGE,
                    speaker="Bob",
                    content="Can you break down the risk?",
                    platform="discord",
                    topic="Collector safety",
                ),
                output_channels=[OutputChannel.API_RESPONSE_ONLY],
            ),
        )
    )

    assert result.cognition_provider_used == "deterministic-fallback"
    assert result.host_text
    assert result.warnings
    assert any("provider unavailable" in error for error in result.errors)
    assert result.dispatch_results[0].status == OutputStatus.SKIPPED
    get_container.cache_clear()


def test_sensitive_host_output_is_not_written_to_memory(tmp_path, monkeypatch) -> None:
    _disable_external_integrations(tmp_path, monkeypatch)
    container = get_container()
    state = _live_session(container, title="Sensitive Memory")

    class SensitiveCognition:
        async def generate(self, request: CognitionRequest) -> CognitionResponse:
            return CognitionResponse(
                request_id=request.request_id,
                provider_name="test-provider",
                text="Do not store this api token secret in memory.",
                confidence=0.9,
            )

    runtime = HostRuntimeService(
        live_sessions=container.live_sessions,
        cognition=SensitiveCognition(),
        sessions=container.sessions,
        transcripts=container.transcripts,
        memory=container.memory,
        output_router=container.output_router,
    )

    result = asyncio.run(
        runtime.execute_turn(
            state.session_id,
            HostTurnRequest(
                event=LiveSessionEventRequest(
                    event_type=LiveEventType.AUDIENCE_QUESTION,
                    speaker="Alice",
                    content="What is safe to remember?",
                    platform="discord",
                ),
                output_channels=[OutputChannel.LOCAL_TEXT],
            ),
        )
    )

    assert result.host_text.startswith("Do not store")
    assert result.transcript_event_id
    assert result.memory_write_ids == []
    assert not any("api token" in hit.lower() for hit in container.memory.semantic.search("general", limit=20))
    get_container.cache_clear()


def test_output_adapters_report_local_sent_and_disabled_discord(tmp_path, monkeypatch) -> None:
    _disable_external_integrations(tmp_path, monkeypatch)
    output = HostOutput(session_id="session-1", text="Host output", channels=[OutputChannel.LOCAL_TEXT])

    local = LocalTextOutputAdapter()
    local_result = asyncio.run(local.dispatch(output, OutputChannel.LOCAL_TEXT))
    assert local_result.status == OutputStatus.SENT
    assert local.history[0].text == "Host output"

    discord = DiscordOutputAdapter(runtime_settings=settings)
    discord_result = asyncio.run(discord.dispatch(output, OutputChannel.DISCORD_TEXT))
    assert discord_result.status == OutputStatus.DISABLED
    assert "disabled" in discord_result.message.lower()
    get_container.cache_clear()


def test_discord_text_adapter_uses_bound_client_when_configured(monkeypatch) -> None:
    sent: list[str] = []

    @dataclass
    class Message:
        id: int = 987

    class Channel:
        async def send(self, text: str) -> Message:
            sent.append(text)
            return Message()

    class Client:
        def is_ready(self) -> bool:
            return True

        def get_channel(self, channel_id: int):
            return Channel() if channel_id == 123 else None

    monkeypatch.setattr(settings, "enable_discord", True)
    monkeypatch.setattr(settings, "discord_bot_token", "test-token")
    monkeypatch.setattr(settings, "discord_allowed_text_channel_ids", [123])

    adapter = DiscordOutputAdapter(runtime_settings=settings)
    adapter.bind_client(Client())
    result = asyncio.run(
        adapter.dispatch(
            HostOutput(session_id="session-1", text="Bound Discord output", channels=[OutputChannel.DISCORD_TEXT]),
            OutputChannel.DISCORD_TEXT,
        )
    )

    assert result.status == OutputStatus.SENT
    assert result.external_id == "987"
    assert sent == ["Bound Discord output"]


def test_output_router_selects_local_when_discord_disabled(tmp_path, monkeypatch) -> None:
    _disable_external_integrations(tmp_path, monkeypatch)
    container = get_container()
    state = _live_session(container, title="Router Selection")
    router = OutputRouter(runtime_settings=settings)

    assert router.select_channels(state) == [OutputChannel.LOCAL_TEXT]
    get_container.cache_clear()


def test_api_turn_route_runs_full_host_turn(tmp_path, monkeypatch) -> None:
    _disable_external_integrations(tmp_path, monkeypatch)

    with TestClient(app) as client:
        create = client.post("/sessions", json={"plan_id": "turn-api", "title": "API Turn", "platform": "discord"})
        assert create.status_code == 200
        session_id = create.json()["session_id"]
        assert client.post(f"/sessions/{session_id}/start").status_code == 200

        response = client.post(
            f"/sessions/{session_id}/turn",
            json={
                "event": {
                    "event_type": "audience_question",
                    "speaker": "Alice",
                    "role": "guest",
                    "content": "What should the room do next?",
                    "platform": "discord",
                },
                "output_channels": ["local_text"],
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["host_text"]
        assert body["transcript_event_id"]
        assert body["dispatch_results"][0]["status"] == "sent"

        transcript = client.get(f"/sessions/{session_id}/transcript")
        assert transcript.status_code == 200
        assert transcript.json()[-1]["speaker"] == "NOESIS"

    get_container.cache_clear()
