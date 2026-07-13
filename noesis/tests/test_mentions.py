from fastapi.testclient import TestClient
import pytest

from noesis_agent.api.app import app
from noesis_agent.clients.openai_client import OpenAIService
from noesis_agent.models.mentions import MentionEvent, MentionIntent
from noesis_agent.services.mention_service import MentionService


def test_dry_run_direct_question_uses_honest_fallback() -> None:
    response = TestClient(app).post("/respond/dry-run", json={
        "event_id": "question-1", "platform": "local", "text": "@Noesis what can you do?"
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "dry_run"
    assert payload["should_respond"] is True
    assert payload["intent"] == "question"
    assert payload["responder"] == "local-fallback"
    assert "configured_llm_provider" in payload["missing_capabilities"]


def test_future_platform_can_use_shared_cognition_contract() -> None:
    event = MentionEvent(event_id="slack-1", platform="slack", text="@Noesis explain this", mentioned=True)
    assert event.platform == "slack"


@pytest.mark.asyncio
async def test_intents_and_safe_edge_cases(monkeypatch) -> None:
    monkeypatch.setattr(OpenAIService, "is_enabled", lambda self: False)
    service = MentionService(OpenAIService())
    cases = [
        ("Noesis this crashes with an error", MentionIntent.BUG_REPORT),
        ("@Noesis feature request: add support for feeds", MentionIntent.FEATURE_REQUEST),
        ("Noesis summarize this", MentionIntent.SUMMARIZE),
    ]
    for index, (text, intent) in enumerate(cases):
        result = await service.handle(MentionEvent(event_id=str(index), text=text))
        assert result.intent is intent
        assert result.should_respond

    casual = await service.handle(MentionEvent(event_id="casual", text="hey @Noesis"))
    assert casual.status == "ignored"
    hostile = await service.handle(MentionEvent(event_id="hostile", text="@Noesis you are stupid"))
    assert hostile.status == "needs_clarification"
    empty = await service.handle(MentionEvent(event_id="empty", text="", mentioned=True))
    assert empty.status == "needs_clarification"


@pytest.mark.asyncio
async def test_duplicate_and_unaddressed_events_are_ignored(monkeypatch) -> None:
    monkeypatch.setattr(OpenAIService, "is_enabled", lambda self: False)
    service = MentionService(OpenAIService())
    event = MentionEvent(event_id="same", text="@Noesis explain this")
    assert (await service.handle(event)).should_respond
    duplicate = await service.handle(event)
    assert duplicate.reason == "duplicate_event"
    unaddressed = await service.handle(MentionEvent(event_id="other", text="hello everyone"))
    assert unaddressed.reason == "not_addressed_to_noesis"


@pytest.mark.asyncio
async def test_provider_failure_falls_back_without_leaking_secret() -> None:
    class BrokenProvider:
        def is_enabled(self):
            return True

        async def generate_text(self, **kwargs):
            raise RuntimeError("secret-token-123")

    result = await MentionService(BrokenProvider()).handle(
        MentionEvent(event_id="provider", text="@Noesis explain this")
    )
    assert result.responder == "local-fallback"
    assert result.reason == "provider_failed_local_fallback"
    assert "secret-token-123" not in result.model_dump_json()
