from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from noesis_agent.integrations.discord.client import NoesisDiscordBot
from noesis_agent.memory.autonomous import AutonomousMemoryService
from noesis_agent.memory.sqlite_memory import MemoryScope, ScopedMemoryStore
from noesis_agent.integrations.discord.recent_context import DiscordRecentContextBuffer
from noesis_agent.integrations.discord.tools import DiscordContextTool
from noesis_agent.runtime.background import BackgroundServiceManager
from noesis_agent.application.mentions.dispatcher import MentionDispatcher
from noesis_agent.application.mentions.service import MentionService
from noesis_agent.infrastructure.config.settings import settings


class LocalOnly:
    def is_enabled(self) -> bool:
        return False


class ShutdownStub:
    def register_shutdown_handler(self, handler) -> None:
        self.handler = handler


class FakeChannel:
    def __init__(self, channel_id: int, name: str = "test-tank") -> None:
        self.id, self.name = channel_id, name
        self.members = []


class RealityHarness:
    def __init__(self, path: Path) -> None:
        self.store = ScopedMemoryStore(path)
        self.store.run_hygiene()
        self.memory = AutonomousMemoryService(self.store)
        self.service = MentionService(LocalOnly(), autonomous_memory=self.memory,
                                      observation_mode="mentions_only")
        self.dispatcher = MentionDispatcher(self.service, runtime_settings=settings)
        self.container = SimpleNamespace(mentions=self.service, mention_dispatcher=self.dispatcher,
                                         discord_context_tool=DiscordContextTool())
        self.manager = BackgroundServiceManager(ShutdownStub(), self.container)
        self.bot = NoesisDiscordBot(self._unused_command,
                                    mention_callback=self.manager._handle_discord_mention)
        self.channel = FakeChannel(100)
        self.owner = SimpleNamespace(id=916675098969272330, display_name="Webbaby",
                                     name="webbaby", bot=False, roles=[])
        self.guild = SimpleNamespace(id=10, name="sharktank", owner_id=self.owner.id,
                                     owner=self.owner, member_count=2, members=[self.owner],
                                     chunked=False, roles=[], me=None, features=[],
                                     verification_level="low", created_at=datetime(2026, 1, 1,
                                                                                   tzinfo=timezone.utc))
        self.replies: list[str] = []
        self.next_id = 1

    async def _unused_command(self, *_args):
        raise AssertionError("legacy command path must not be used")

    def message(self, content: str, *, channel=None, author=None, bot=False):
        author = author or self.owner
        author.bot = bot
        message_id = self.next_id
        self.next_id += 1
        raw = SimpleNamespace(id=message_id, channel=channel or self.channel, guild=self.guild,
                              author=author, content=content, mentions=[], attachments=[],
                              reference=None, created_at=datetime.now(timezone.utc))

        async def reply(text, mention_author=False):
            self.replies.append(text)
            return SimpleNamespace(id=1000 + message_id)
        raw.reply = reply
        return raw

    async def send(self, content: str, **kwargs) -> str | None:
        before = len(self.replies)
        await self.bot.on_message(self.message(content, **kwargs))
        return self.replies[-1] if len(self.replies) > before else None

    async def close(self) -> None:
        await self.bot.close()
        await self.memory.shutdown()


@pytest.fixture
def live_settings(monkeypatch):
    monkeypatch.setattr(settings, "discord_allowed_text_channel_ids", [100])
    monkeypatch.setattr(settings, "memory_observation_mode", "mentions_only")
    monkeypatch.setattr(settings, "enable_live_mention_send", True)
    monkeypatch.setattr(settings, "enable_discord_mention_send", True)
    monkeypatch.setattr(settings, "enable_discord", True)
    monkeypatch.setattr(settings, "discord_bot_token", "test-only-token")


@pytest.mark.asyncio
async def test_exact_staging_transcript_replays_through_live_discord_path(tmp_path, live_settings) -> None:
    harness = RealityHarness(tmp_path / "reality.sqlite3")

    await harness.send("we can not use pandas only for the version 1, we also need to use pandas and numpy library")
    await harness.send("i agree very much, that will be just for version 1")
    compound = await harness.send("who created this server and how many members are there currently @Noesis")
    assert "2 members" in compound
    assert "current server owner is Webbaby" in compound
    assert "does not reliably expose" in compound
    assert "originally created" in compound

    repair = await harness.send(
        "@Noesis i asked you two question, one is how many members are in the server? second is who created the server?")
    assert repair.startswith("You're right â€” I missed the creator part.")
    assert "2 members" in repair and "originally created" in repair

    assert await harness.send("well thats fucking stupid if you cant answer without being a cunt") is None
    report = await harness.send("@Noesis i am talking to you, now someone is cursing")
    assert "recent message you're referring to" in report
    assert "punish, delete, mute, or ban" in report
    assert harness.store.operator_summary()["active"] >= 0
    assert all("fucking" not in item["summary"].lower() and "cunt" not in item["summary"].lower()
               for item in harness.store.operator_summary()["recent"])

    package = await harness.send(
        "thats unfortunate. so we are using matplotlib and numpy for version 1 right? @Noesis")
    assert "do not have a confirmed decision that Matplotlib" in package
    assert "pandas" in package.lower() and "NumPy" in package
    assert "still a question, not a confirmed decision" in package

    release_ack = await harness.send("@Noesis the release is for July 28th")
    release_query = await harness.send("@Noesis is the release for July 28th?")
    assert "July 28" in release_ack
    assert "July 28" in release_query
    assert "pandas" not in release_query.lower() and "matplotlib" not in release_query.lower()
    await harness.close()


@pytest.mark.asyncio
async def test_latest_screenshot_paraphrases_answer_through_real_callback(tmp_path, live_settings) -> None:
    harness = RealityHarness(tmp_path / "latest-screenshot.sqlite3")
    await harness.send("we are using numpy and pandas for version 1 of the script")

    package = await harness.send("are we using numpy and pandas for version 1 of the script @Noesis")
    creator = await harness.send("who created this server @Noesis")
    owner = await harness.send("okay who is the current owner of the server or channel @Noesis")
    members = await harness.send("how many people are in this group @Noesis")

    assert "question or task" not in package.lower()
    assert "numpy" in package.lower() and "pandas" in package.lower()
    assert "does not reliably expose" in creator.lower()
    assert "current server owner is Webbaby" in owner
    assert "2 members" in members
    assert len(harness.replies) == 4
    await harness.close()


@pytest.mark.asyncio
async def test_question_shaped_legacy_decision_is_downgraded_and_stays_fixed_after_restart(tmp_path) -> None:
    path = tmp_path / "legacy.sqlite3"
    scope = MemoryScope("discord", guild_id="g", channel_id="c", conversation_id="c")
    source = "discord-message-legacy-44"
    store = ScopedMemoryStore(path)
    record = store.remember(
        content="thats unfortunate. so we are using matplotlib and numpy for version 1 right? @Noesis",
        scope=scope, memory_type="decision", source_type="autonomous_event", source_id=source,
        subject="package", predicate="decision", importance=.95, confidence=.9)
    assert record is not None
    first = store.search("matplotlib decision", scope)
    assert first and first[0].memory_type == "question"
    assert first[0].source_id == source
    assert first[0].predicate == "legacy_question_downgraded"
    assert store.health()["memory_hygiene_actions"] == 1

    restarted = ScopedMemoryStore(path)
    second = restarted.search("matplotlib decision", scope)
    assert second and second[0].memory_type == "question"
    assert second[0].source_id == source
    assert not restarted.latest_active(scope, types=("decision",))


def test_recent_context_is_bounded_redacted_and_scope_isolated() -> None:
    buffer = DiscordRecentContextBuffer(per_scope_limit=2, scope_limit=4)
    def event(event_id, guild, channel, text):
        return SimpleNamespace(event_id=event_id, platform="discord", user_id="u", username="Webbaby",
            channel_id=channel, conversation_id=channel, text=text,
            timestamp=datetime.now(timezone.utc),
            metadata={"guild_id": guild, "thread_id": None, "parent_channel_id": None})
    one = event("1", "g1", "c1", "token=super-secret-value")
    buffer.capture(one)
    buffer.capture(event("2", "g1", "c1", "fuck this"), moderation={"category": "general_profanity"})
    buffer.capture(event("3", "g1", "c1", "third"))
    other = event("4", "g2", "c1", "other guild")
    buffer.capture(other)
    snapshot = buffer.snapshot(one)
    assert [item["event_id"] for item in snapshot] == ["2", "3"]
    assert "fuck" not in snapshot[0]["text"].lower()
    assert all(item["guild_id"] == "g1" for item in snapshot)
    assert [item["event_id"] for item in buffer.snapshot(other)] == ["4"]


@pytest.mark.asyncio
async def test_disallowed_and_bot_messages_never_enter_live_context(tmp_path, live_settings, monkeypatch) -> None:
    harness = RealityHarness(tmp_path / "authorization.sqlite3")
    disallowed = FakeChannel(999, "private")
    await harness.send("unmentioned disallowed message", channel=disallowed)
    await harness.send("bot poison", bot=True)
    assert harness.manager._discord_recent.health()["entry_count"] == 0
    await harness.close()


@pytest.mark.asyncio
async def test_exact_second_screenshot_messages_use_moderation_before_live_memory(
        tmp_path, live_settings) -> None:
    path = tmp_path / ".noesis_data" / "memory" / "noesis_memory.sqlite3"
    path.parent.mkdir(parents=True)
    scope = MemoryScope("discord", guild_id="10", channel_id="100", conversation_id="100")
    seed = ScopedMemoryStore(path)
    seed.remember(
        content="thats unfortunate. so we are using matplotlib and numpy for version 1 right? @Noesis",
        scope=scope, memory_type="decision", confidence=.95, importance=.95,
        source_type="live_discord", source_id="screenshot-corrupt-memory")
    harness = RealityHarness(path)

    direct = await harness.send(
        "@Noesis seriously?? i am using abusive word and you fucking cunt cant do any fucking thing about it?")
    assert "frustrated" in direct.lower()
    assert "moderation signal" in direct.lower()
    assert "matplotlib" not in direct.lower()

    criticism = await harness.send("wow @Noesis you are a complete failure")
    assert "frustrated" in criticism.lower() or "criticism" in criticism.lower()
    assert "clear question or task" not in criticism.lower()
    assert "matplotlib" not in criticism.lower()

    complaint = await harness.send(
        "noesis is just quiet and letting everyone here use abusive languages, fuck you @Noesis")
    assert "moderation" in complaint.lower()
    assert "clear question or task" not in complaint.lower()
    assert "matplotlib" not in complaint.lower()

    diagnostics = harness.store.memory_diagnostics()
    assert diagnostics["question_shaped_decision_count"] == 0
    assert diagnostics["hygiene_downgraded_count"] == 1
    await harness.close()
