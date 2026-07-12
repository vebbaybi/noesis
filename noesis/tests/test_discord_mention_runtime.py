from __future__ import annotations

from types import SimpleNamespace

import pytest

from noesis_agent.config.settings import Settings, settings
from noesis_agent.models.mentions import MentionEvent
from noesis_agent.services.background import BackgroundServiceManager
from noesis_agent.services.mention_dispatcher import MentionDispatcher
from noesis_agent.services.mention_service import MentionService


class DisabledProvider:
    def is_enabled(self):
        return False


def runtime_settings(**overrides) -> Settings:
    values = {
        "NOESIS_ENABLE_DISCORD": True,
        "DISCORD_BOT_TOKEN": "test-token-value",
        "NOESIS_ENABLE_LIVE_MENTION_SEND": True,
        "NOESIS_ENABLE_DISCORD_MENTION_SEND": True,
        "NOESIS_ENABLE_X": False,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_live_mock_sender_sends_once_and_duplicate_is_suppressed() -> None:
    calls: list[str] = []

    async def sender(text: str):
        calls.append(text)
        return SimpleNamespace(id=456)

    dispatcher = MentionDispatcher(MentionService(DisabledProvider()),
        runtime_settings=runtime_settings())
    event = MentionEvent(event_id="discord-once", platform="discord",
                         text="@Noesis explain this")
    first = await dispatcher.dispatch(event, live=True, discord_sender=sender)
    second = await dispatcher.dispatch(event, live=True, discord_sender=sender)
    assert first.send_mode == "succeeded"
    assert first.send_attempted is True
    assert first.sent_message_id == "456"
    assert second.response_status == "ignored"
    assert second.disabled_reason == "duplicate_event"
    assert calls and len(calls) == 1


@pytest.mark.asyncio
async def test_sender_failure_is_sanitized() -> None:
    async def sender(_text: str):
        raise RuntimeError("test-token-value must never leak")

    dispatcher = MentionDispatcher(MentionService(DisabledProvider()),
        runtime_settings=runtime_settings())
    result = await dispatcher.dispatch(MentionEvent(event_id="discord-failure", platform="discord",
        text="@Noesis explain this"), live=True, discord_sender=sender)
    assert result.send_mode == "failed"
    assert result.send_attempted is True
    assert result.error_category == "platform_send_error"
    assert "test-token-value" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_explicit_live_switches_are_required() -> None:
    called = False

    async def sender(_text: str):
        nonlocal called
        called = True

    dispatcher = MentionDispatcher(MentionService(DisabledProvider()), runtime_settings=runtime_settings(
        NOESIS_ENABLE_LIVE_MENTION_SEND=False,
    ))
    result = await dispatcher.dispatch(MentionEvent(event_id="discord-disabled", platform="discord",
        text="@Noesis explain this"), live=True, discord_sender=sender)
    assert result.send_mode == "disabled"
    assert "configuration" in result.disabled_reason
    assert called is False


@pytest.mark.asyncio
async def test_background_runtime_uses_original_message_reply(monkeypatch) -> None:
    monkeypatch.setattr(settings, "enable_live_mention_send", True)
    monkeypatch.setattr(settings, "enable_discord_mention_send", True)
    replies: list[tuple[str, bool]] = []

    class Message:
        async def reply(self, text: str, mention_author: bool):
            replies.append((text, mention_author))
            return SimpleNamespace(id=789)

    dispatcher = MentionDispatcher(MentionService(DisabledProvider()),
        runtime_settings=runtime_settings())
    container = SimpleNamespace(mention_dispatcher=dispatcher)
    shutdown = SimpleNamespace(register_shutdown_handler=lambda handler: None)
    manager = BackgroundServiceManager(shutdown, container=container)
    await manager._handle_discord_mention(
        MentionEvent(event_id="runtime-message", platform="discord", text="@Noesis explain this"),
        Message(),
    )
    assert len(replies) == 1
    assert replies[0][1] is False
