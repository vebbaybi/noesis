from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from noesis_agent.api.app import app
from noesis_agent.config.settings import Settings
from noesis_agent.models.mentions import MentionEvent
from noesis_agent.platforms.mention_normalizers import normalize_discord_message, normalize_x_mention
from noesis_agent.services.mention_dispatcher import MentionDispatcher
from noesis_agent.services.mention_service import MentionService


class DisabledProvider:
    def is_enabled(self):
        return False


def disabled_settings(**overrides):
    values = {"NOESIS_ENABLE_DISCORD": False, "DISCORD_BOT_TOKEN": "",
              "NOESIS_ENABLE_LIVE_MENTION_SEND": False,
              "NOESIS_ENABLE_DISCORD_MENTION_SEND": False,
              "NOESIS_ENABLE_X": False, "X_API_KEY": "", "X_API_SECRET": "",
              "X_ACCESS_TOKEN": "", "X_ACCESS_TOKEN_SECRET": ""}
    values.update(overrides)
    return Settings(**values)


def test_discord_normalizer_extracts_reply_context_and_attachment() -> None:
    bot = SimpleNamespace(id=99, bot=True, name="Noesis")
    parent = SimpleNamespace(content="parent context", author=bot)
    message = SimpleNamespace(
        id=123, content="please summarize this", author=SimpleNamespace(id=7, display_name="Ada"),
        channel=SimpleNamespace(id=8, parent_id=4), guild=SimpleNamespace(id=9), mentions=[],
        reference=SimpleNamespace(resolved=parent), created_at=datetime.now(timezone.utc),
        attachments=[SimpleNamespace(id=5, filename="note.txt", url="https://example.invalid/note")],
    )
    event = normalize_discord_message(message, bot_user_id=99, thread_type=SimpleNamespace)
    assert event.platform == "discord"
    assert event.event_id == "123"
    assert event.is_reply_to_noesis
    assert event.parent_text == "parent context"
    assert event.metadata["thread_id"] == "8"
    assert event.attachments[0]["filename"] == "note.txt"


def test_x_normalizer_extracts_mention_and_context() -> None:
    event = normalize_x_mention({"id": "42", "text": "@Noesis explain this", "author_id": "7",
        "author_username": "ada", "conversation_id": "40", "parent_text": "context",
        "media": [{"media_key": "m1"}]}, handle="Noesis")
    assert event.platform == "x"
    assert event.mentioned is True
    assert event.parent_text == "context"
    assert event.conversation_id == "40"


@pytest.mark.asyncio
async def test_normalized_events_flow_through_service_and_dedupe() -> None:
    service = MentionService(DisabledProvider())
    discord = normalize_discord_message({"id": "d1", "content": "@Noesis bug: it crashes",
        "author": {"id": "u1", "name": "Ada"}}, bot_name="Noesis")
    x = normalize_x_mention({"id": "x1", "text": "@Noesis feature request: add feeds"})
    assert (await service.handle(discord)).intent.value == "bug_report"
    assert (await service.handle(x)).intent.value == "feature_request"
    assert (await service.handle(x)).reason == "duplicate_event"


@pytest.mark.asyncio
async def test_dispatcher_dry_run_never_sends() -> None:
    calls = []
    async def sender(text):
        calls.append(text)
    dispatcher = MentionDispatcher(MentionService(DisabledProvider()),
        runtime_settings=disabled_settings(), discord_sender=sender)
    result = await dispatcher.dispatch(MentionEvent(event_id="d2", platform="discord",
        text="@Noesis explain this"), live=False)
    assert result.send_mode == "dry_run"
    assert result.send_attempted is False
    assert calls == []


@pytest.mark.asyncio
async def test_live_disabled_reports_missing_credentials_without_secrets() -> None:
    dispatcher = MentionDispatcher(MentionService(DisabledProvider()), runtime_settings=disabled_settings(
        NOESIS_ENABLE_LIVE_MENTION_SEND=True, NOESIS_ENABLE_DISCORD_MENTION_SEND=True,
    ))
    discord = await dispatcher.dispatch(MentionEvent(event_id="d3", platform="discord",
        text="@Noesis explain this"), live=True)
    assert discord.send_mode == "disabled"
    assert discord.missing_credentials == ["DISCORD_BOT_TOKEN"]
    x = await dispatcher.dispatch(MentionEvent(event_id="x3", platform="x",
        text="@Noesis explain this"), live=True)
    assert "X_API_KEY" in x.missing_credentials
    serialized = discord.model_dump_json() + x.model_dump_json()
    assert "secret-token-123" not in serialized
    assert "api_key_value" not in serialized


def test_raw_api_simulates_discord_and_x_without_live_send() -> None:
    client = TestClient(app)
    discord = client.post("/events/mention/raw/test", json={"platform": "discord",
        "bot_user_id": "99", "event": {"id": "api-d", "content": "<@99> explain this",
        "author": {"id": "7"}, "mentions": [{"id": "99"}]}})
    assert discord.status_code == 200
    assert discord.json()["send_mode"] == "dry_run"
    x = client.post("/events/mention/raw/test", json={"platform": "x",
        "event": {"id": "api-x", "text": "@Noesis explain this"}})
    assert x.status_code == 200
    assert x.json()["send_attempted"] is False


def test_readme_states_live_integrations_are_unverified() -> None:
    text = open("README.md", encoding="utf-8").read().lower()
    assert "live replies are disabled by default" in text
    assert "have not been verified against discord" in text
    assert "x live delivery" in text and "unverified" in text
