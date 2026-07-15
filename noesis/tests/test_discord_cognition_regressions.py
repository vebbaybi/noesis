from pathlib import Path

import pytest

from noesis_agent.cognition.capabilities import CapabilityRegistry
from noesis_agent.memory.autonomous import AutonomousMemoryService, CandidateExtractor
from noesis_agent.memory.sqlite_memory import MemoryScope, ScopedMemoryStore
from noesis_agent.domain.contracts.mentions import MentionEvent
from noesis_agent.application.mentions.service import MentionService


class LocalOnly:
    def is_enabled(self) -> bool:
        return False


class EnabledProvider:
    def __init__(self) -> None:
        self.calls = 0

    def is_enabled(self) -> bool:
        return True

    async def generate_text(self, **kwargs) -> str:
        self.calls += 1
        return "provider should not replace local facts"


SCOPE = MemoryScope("discord", guild_id="g", channel_id="c", conversation_id="c")


def registry() -> CapabilityRegistry:
    return CapabilityRegistry(Path("../assets/users_request.md"))


def discord_event(event_id: str, text: str, **metadata) -> MentionEvent:
    return MentionEvent(event_id=event_id, platform="discord", text=text, mentioned=True,
                        channel_id="c", conversation_id="c",
                        metadata={"guild_id": "g", **metadata})


def evidence(owner="Webbaby", count=2) -> list[dict]:
    return [{"facts": {"guild_owner_id": "916675098969272330",
                        "guild_owner_display_name": owner, "member_count": count,
                        "channel_name": "general", "is_thread": False}}]


def test_compound_capability_route_preserves_every_requested_intent() -> None:
    route = registry().route(platform="discord",
        text="who owns this server and how many members are here?", intent="question")
    assert [item["capability_id"] for item in route["matches"]] == [
        "discord.guild.owner", "discord.guild.member_count"]


@pytest.mark.asyncio
async def test_compound_discord_answer_uses_owner_name_and_member_count() -> None:
    service = MentionService(LocalOnly(), capability_registry=registry())
    event = discord_event("compound", "@Noesis who owns this server and how many members are here?",
                          evidence=evidence())
    response = await service.handle(event, dry_run=True)
    assert response.text == "The current server owner is Webbaby, and this server currently has 2 members."
    assert "916675098969272330" not in response.text
    assert response.metadata["response_plan"]["compound_capabilities"] == [
        "discord.guild.owner", "discord.guild.member_count"]


@pytest.mark.asyncio
async def test_local_discord_evidence_precedes_enabled_external_provider() -> None:
    provider = EnabledProvider()
    service = MentionService(provider, capability_registry=registry())
    event = discord_event("local-first", "@Noesis who owns this server?", evidence=evidence())
    response = await service.handle(event, dry_run=True)
    assert response.text == "The current server owner is Webbaby."
    assert provider.calls == 0
    assert response.metadata["response_plan"]["provider_reason"] == "local_context_preferred"


@pytest.mark.asyncio
async def test_follow_up_repair_acknowledges_omission_and_answers() -> None:
    service = MentionService(LocalOnly(), capability_registry=registry())
    event = discord_event("repair", "@Noesis well I also asked how many members?",
                          evidence=evidence(), previous_noesis_response="The current server owner is Webbaby.")
    response = await service.handle(event, dry_run=True)
    assert response.text.startswith("You're right â€” I missed that part.")
    assert "2 members" in response.text


@pytest.mark.asyncio
async def test_moderation_report_uses_bounded_context_without_punishment(tmp_path: Path) -> None:
    memory = AutonomousMemoryService(ScopedMemoryStore(tmp_path / "moderation.sqlite3"))
    service = MentionService(LocalOnly(), autonomous_memory=memory, capability_registry=registry())
    event = discord_event("report", "@Noesis somebody is cursing in the group",
                          recent_context=[{"event_id": "bad", "author": "member",
                                           "text": "fuck everybody in this server"}])
    response = await service.handle(event, dry_run=False)
    assert response.intent.value == "moderation_report"
    assert "hostile" in response.text.lower() or "profan" in response.text.lower()
    assert "human moderator" in response.text.lower()
    assert "not punish" in response.text.lower()
    assert response.metadata["response_plan"]["used_recent_context"] is True
    await memory.shutdown()


@pytest.mark.asyncio
async def test_ambient_hostility_is_classified_silently_and_not_memorized(tmp_path: Path) -> None:
    memory = AutonomousMemoryService(ScopedMemoryStore(tmp_path / "ambient.sqlite3"))
    service = MentionService(LocalOnly(), autonomous_memory=memory,
                             observation_mode="observe_and_moderate")
    event = MentionEvent(event_id="ambient", platform="discord", text="fuck everybody",
                         mentioned=False, channel_id="c", conversation_id="c",
                         metadata={"guild_id": "g", "observation_mode": "observe_and_moderate"})
    response = await service.handle(event, dry_run=False)
    assert response.should_respond is False
    assert response.metadata["moderation"]["category"].endswith("profanity")
    assert response.metadata["memory"]["persisted"] == 0
    assert memory.health()["moderation_signals"] == 1
    assert memory.store.operator_summary()["active"] == 0
    await memory.shutdown()


def test_memory_extraction_separates_decision_question_and_release_fact() -> None:
    extractor = CandidateExtractor()
    rejected = extractor.extract("PostgreSQL is overkill for this version. We should not use it.",
                                 platform="discord", event_id="d", scope=SCOPE)[0]
    question = extractor.extract("we are using MySQL for this version right?",
                                 platform="discord", event_id="q", scope=SCOPE)[0]
    release = extractor.extract("@Noesis the release is for july28th",
                                platform="discord", event_id="r", scope=SCOPE)[0]
    assert (rejected.candidate_type, rejected.subject, rejected.predicate) == (
        "decision", "database", "rejected_option")
    assert rejected.content == "PostgreSQL should not be used for this version."
    assert question.candidate_type == "question" and question.predicate == "open_question"
    assert release.candidate_type == "fact" and release.object_value == "July 28"
    assert release.content == "The planned release date is July 28."


@pytest.mark.asyncio
async def test_topic_retrieval_never_substitutes_database_decision_for_release(tmp_path: Path) -> None:
    memory = AutonomousMemoryService(ScopedMemoryStore(tmp_path / "topics.sqlite3"))
    await memory.process("PostgreSQL is overkill. We should not use it.", scope=SCOPE,
                         platform="discord", event_id="db")
    await memory.process("the release is for July 28th", scope=SCOPE,
                         platform="discord", event_id="release")
    release_hits = await memory.retrieve("is the version release for July 28th?", SCOPE)
    database_hits = await memory.retrieve("what database storage decision did we make?", SCOPE)
    assert release_hits and release_hits[0].subject == "release"
    assert database_hits and database_hits[0].subject == "database"
    assert "PostgreSQL" not in release_hits[0].content
    await memory.shutdown()


@pytest.mark.asyncio
async def test_declarative_release_fact_gets_natural_local_acknowledgement(tmp_path: Path) -> None:
    memory = AutonomousMemoryService(ScopedMemoryStore(tmp_path / "fact.sqlite3"))
    service = MentionService(LocalOnly(), autonomous_memory=memory)
    response = await service.handle(discord_event("fact", "@Noesis the release is for july28th"),
                                    dry_run=False)
    assert "July 28" in response.text
    assert "project fact" in response.text
    assert "external knowledge provider" not in response.text
    await memory.shutdown()
