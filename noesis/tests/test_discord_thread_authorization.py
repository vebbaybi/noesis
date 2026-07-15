from __future__ import annotations

from types import SimpleNamespace

import pytest

from noesis_agent.integrations.discord.client import NoesisDiscordBot
from noesis_agent.infrastructure.config.settings import settings
from noesis_agent.integrations.discord.authorization import authorize_discord_message
from noesis_agent.integrations.mention_normalizers import normalize_discord_message
from noesis_agent.application.mentions.service import MentionService


class FakeThread:
    def __init__(self, thread_id: int, parent_id: int | None, *, parent=None) -> None:
        self.id = thread_id
        self.parent_id = parent_id
        self.parent = parent


class FakeTextChannel:
    def __init__(self, channel_id: int, *, parent_id: int | None = None) -> None:
        self.id = channel_id
        self.parent_id = parent_id


def message(channel, *, message_id: int = 1, guild_id: int | None = 10):
    return SimpleNamespace(
        id=message_id, channel=channel,
        guild=SimpleNamespace(id=guild_id) if guild_id is not None else None,
        author=SimpleNamespace(id=20, name="operator"), content="@Noesis explain this",
        mentions=[], attachments=[], reference=None,
    )


@pytest.mark.parametrize(
    ("channel", "allowed", "expected", "reason"),
    [
        (FakeTextChannel(100), [100], True, "authorized"),
        (FakeTextChannel(101), [100], False, "channel_not_allowlisted"),
        (FakeThread(200, 100), [100], True, "authorized"),
        (FakeThread(201, 101), [100], False, "thread_parent_not_allowlisted"),
        (FakeThread(202, None), [100], False, "thread_parent_unresolved"),
        (FakeTextChannel(203, parent_id=100), [100], False, "channel_not_allowlisted"),
        (FakeThread(204, 101), [204], True, "authorized"),
    ],
)
def test_discord_channel_authorization_matrix(channel, allowed, expected, reason) -> None:
    decision = authorize_discord_message(message(channel), allowed, thread_type=FakeThread)
    assert decision.allowed is expected
    assert decision.reason == reason


def test_thread_parent_object_fallback_and_normalized_lineage() -> None:
    raw = message(FakeThread(300, None, parent=SimpleNamespace(id=100)), message_id=55)
    decision = authorize_discord_message(raw, [100], thread_type=FakeThread)
    event = normalize_discord_message(raw, authorization=decision, thread_type=FakeThread)
    assert decision.allowed
    assert decision.authorization_source == "thread_parent"
    assert event.metadata == {
        "message_id": "55", "current_channel_id": "300", "thread_id": "300",
        "parent_channel_id": "100", "guild_id": "10", "is_thread": True,
        "authorization_source": "thread_parent", "authorization_reason": "authorized",
        "response_target_id": "300", "channel_type": "FakeThread",
    }
    assert event.channel_id == "300"
    assert event.conversation_id == "300"


def test_same_thread_different_messages_are_not_duplicates() -> None:
    first = normalize_discord_message(message(FakeThread(300, 100), message_id=1), thread_type=FakeThread)
    second = normalize_discord_message(message(FakeThread(300, 100), message_id=2), thread_type=FakeThread)
    assert first.event_id != second.event_id


@pytest.mark.asyncio
async def test_rejected_thread_stops_before_cognition_or_send() -> None:
    callbacks = 0
    async def command_callback(*_args):
        raise AssertionError("command processing must not run")
    async def mention_callback(*_args):
        nonlocal callbacks
        callbacks += 1
    bot = NoesisDiscordBot(command_callback, mention_callback=mention_callback)
    raw = message(FakeThread(301, 999))
    raw.author.bot = False
    decision = authorize_discord_message(raw, [100], thread_type=FakeThread)
    bot._extract_text_prompt = lambda _message: "explain this"
    bot._ensure_allowed_message_channel = lambda _message: _async_value(decision)
    await bot.on_message(raw)
    assert callbacks == 0
    await bot.close()


def test_missing_guild_rejects_safely() -> None:
    decision = authorize_discord_message(message(FakeTextChannel(100), guild_id=None), [100], thread_type=FakeThread)
    assert not decision.allowed
    assert decision.reason == "guild_context_missing"


@pytest.mark.asyncio
async def test_duplicate_cache_is_bounded_and_platform_scoped() -> None:
    class Provider:
        def is_enabled(self):
            return False
    service = MentionService(Provider(), duplicate_limit=2)
    for event_id in ("1", "2", "3"):
        await service.handle(normalize_discord_message(
            message(FakeTextChannel(100), message_id=int(event_id)), thread_type=FakeThread
        ))
    assert len(service._seen) == 2
    x_event = normalize_discord_message(message(FakeTextChannel(100), message_id=3), thread_type=FakeThread)
    x_event.platform = "x"
    assert (await service.handle(x_event)).reason != "duplicate_event"


async def _async_value(value):
    return value


@pytest.mark.asyncio
async def test_authorized_unmentioned_message_reaches_ambient_callback_when_enabled(monkeypatch) -> None:
    received = []
    async def command_callback(command, payload): return "unused"
    async def mention_callback(event, raw): received.append(event)
    monkeypatch.setattr(settings, "memory_observation_mode", "observe_and_remember")
    monkeypatch.setattr(settings, "discord_allowed_text_channel_ids", [100])
    bot = NoesisDiscordBot(command_callback, mention_callback=mention_callback)
    raw = message(FakeTextChannel(100), message_id=501)
    raw.content = "Agreed. We are staying with SQLite for V1."
    await bot.on_message(raw)
    assert len(received) == 1
    assert received[0].mentioned is False
    assert received[0].metadata["observation_mode"] == "observe_and_remember"
    await bot.close()
