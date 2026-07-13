from pathlib import Path

import pytest

from noesis_agent.memory.autonomous import AutonomousMemoryService
from noesis_agent.memory.sqlite_memory import MemoryScope, ScopedMemoryStore
from noesis_agent.models.mentions import MentionEvent
from noesis_agent.services.mention_service import MentionService


class DisabledProvider:
    def is_enabled(self): return False


def scope(guild="g1", channel="c1", conversation="t1"):
    return MemoryScope("discord", guild_id=guild, channel_id=channel, conversation_id=conversation)


@pytest.mark.asyncio
async def test_decision_task_blocker_and_low_value_write_gate(tmp_path: Path) -> None:
    service = AutonomousMemoryService(ScopedMemoryStore(tmp_path / "memory.sqlite3"))
    assert len((await service.process("Agreed. We are staying with SQLite for V1.", scope=scope(), platform="discord", event_id="1"))["accepted"]) == 1
    assert len((await service.process("Daniel will update the operator documentation by Friday.", scope=scope(), platform="discord", event_id="2"))["accepted"]) == 1
    assert len((await service.process("Live X verification is blocked because credentials are unavailable.", scope=scope(), platform="discord", event_id="3"))["accepted"]) == 1
    assert not (await service.process("lol gm", scope=scope(), platform="discord", event_id="4"))["accepted"]
    rejected = await service.process("API_TOKEN=super-secret-value", scope=scope(), platform="discord", event_id="5")
    assert rejected["rejected"][0]["rejection_reason"] == "sensitive_content"


@pytest.mark.asyncio
async def test_replay_scope_restart_and_correction(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite3"
    service = AutonomousMemoryService(ScopedMemoryStore(path))
    await service.process("The release is August 1.", scope=scope(), platform="discord", event_id="1")
    await service.process("Correction, the release moved to August 15.", scope=scope(), platform="discord", event_id="2")
    await service.process("Correction, the release moved to August 15.", scope=scope(), platform="discord", event_id="2")
    restarted = AutonomousMemoryService(ScopedMemoryStore(path))
    hits = await restarted.retrieve("release August", scope())
    assert len(hits) == 1 and "August 15" in hits[0].content
    assert not await restarted.retrieve("release August", scope(guild="g2"))


def test_task_candidate_resolves_assignee_deadline_and_status(tmp_path: Path) -> None:
    service = AutonomousMemoryService(ScopedMemoryStore(tmp_path / "memory.sqlite3"))
    candidate = service.extractor.extract("Daniel will update the operator documentation by Friday.",
        platform="discord", event_id="task", scope=scope())[0]
    assert candidate.candidate_type == "task"
    assert candidate.assignee == "Daniel"
    assert candidate.deadline.lower() == "friday"
    assert candidate.task_status == "open"


@pytest.mark.asyncio
async def test_task_completion_supersedes_open_task(tmp_path: Path) -> None:
    service = AutonomousMemoryService(ScopedMemoryStore(tmp_path / "memory.sqlite3"))
    await service.process("Daniel will update the README by Friday.", scope=scope(),
                          platform="discord", event_id="task-open")
    await service.process("README update is done.", scope=scope(),
                          platform="discord", event_id="task-done")
    active = await service.retrieve("README update", scope())
    assert len(active) == 1
    assert active[0].task_status == "completed"
    assert service.store.operator_summary()["superseded"] == 1
    await service.shutdown()


@pytest.mark.asyncio
async def test_reply_resolves_parent_task_and_confirmation_reinforces_without_duplicates(tmp_path: Path) -> None:
    memory = AutonomousMemoryService(ScopedMemoryStore(tmp_path / "memory.sqlite3"))
    mentions = MentionService(DisabledProvider(), autonomous_memory=memory,
                              observation_mode="observe_and_remember")
    metadata = {"guild_id": "g1", "authorization_reason": "authorized"}
    await mentions.handle(MentionEvent(event_id="task", platform="discord",
        text="Sam will update the README tomorrow.", mentioned=False, channel_id="c1",
        conversation_id="t1", metadata=metadata), dry_run=False)
    await mentions.handle(MentionEvent(event_id="reply", platform="discord", text="Done.",
        parent_text="Sam will update the README tomorrow.", mentioned=False, channel_id="c1",
        conversation_id="t1", metadata=metadata), dry_run=False)
    completed = await memory.retrieve("README", scope())
    assert len(completed) == 1 and completed[0].task_status == "completed"

    await memory.process("Agreed. We are staying with SQLite for V1.", scope=scope(),
                         platform="discord", event_id="confirm-1")
    first = (await memory.retrieve("SQLite", scope()))[0]
    await memory.process("Agreed, we are staying with SQLite for V1.", scope=scope(),
                         platform="discord", event_id="confirm-2")
    decisions = [item for item in await memory.retrieve("SQLite", scope()) if item.memory_type == "decision"]
    assert len(decisions) == 1 and decisions[0].confidence > first.confidence
    await memory.shutdown()


@pytest.mark.asyncio
async def test_ambient_message_persists_silently_and_later_recall_is_natural(tmp_path: Path) -> None:
    memory = AutonomousMemoryService(ScopedMemoryStore(tmp_path / "memory.sqlite3"))
    mentions = MentionService(DisabledProvider(), autonomous_memory=memory,
                              observation_mode="observe_and_remember")
    metadata = {"guild_id": "g1", "authorization_reason": "authorized"}
    observed = await mentions.handle(MentionEvent(event_id="1", platform="discord", text="Agreed. We are staying with SQLite for V1.", channel_id="c1", conversation_id="t1", mentioned=False, metadata=metadata), dry_run=False)
    assert observed.should_respond is False
    assert observed.metadata["memory"]["persisted"] == 1
    recalled = await mentions.handle(MentionEvent(event_id="2", platform="discord", text="@Noesis why are we using SQLite?", channel_id="c1", conversation_id="t1", mentioned=True, metadata=metadata), dry_run=False)
    assert "active decision" in recalled.text.lower()
