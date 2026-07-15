from pathlib import Path

import pytest

from noesis_agent.memory.autonomous import AutonomousMemoryService
from noesis_agent.memory.sqlite_memory import MemoryScope, ScopedMemoryStore
from noesis_agent.domain.contracts.mentions import MentionEvent
from noesis_agent.application.mentions.service import MentionService


class LocalOnly:
    def is_enabled(self): return False


SCOPE = MemoryScope("discord", guild_id="guild-a", channel_id="channel-a", conversation_id="thread-a")


def event(event_id: str, text: str, *, mentioned: bool = False, guild: str = "guild-a") -> MentionEvent:
    return MentionEvent(event_id=event_id, platform="discord", text=text, mentioned=mentioned,
                        channel_id="channel-a", conversation_id="thread-a",
                        metadata={"guild_id": guild, "authorization_reason": "authorized",
                                  "observation_mode": "observe_and_remember"})


@pytest.mark.asyncio
async def test_all_eight_memory_acceptance_scenarios(tmp_path: Path) -> None:
    path = tmp_path / "acceptance.sqlite3"
    memory = AutonomousMemoryService(ScopedMemoryStore(path))
    cognition = MentionService(LocalOnly(), autonomous_memory=memory,
                               observation_mode="observe_and_remember")

    # 1: two-message discussion produces one canonical decision and natural later recall.
    await cognition.handle(event("d1", "PostgreSQL is overkill for this version."), dry_run=False)
    await cognition.handle(event("d2", "Agreed. We are staying with SQLite for V1."), dry_run=False)
    decisions = await memory.retrieve("SQLite storage", SCOPE)
    assert len(decisions) == 1 and decisions[0].source_id
    recall = await cognition.handle(event("d3", "@Noesis why are we using SQLite?", mentioned=True), dry_run=False)
    assert "active decision" in recall.text.lower() and "SQLite" in recall.text

    # 2: task fields are extracted, retained, then completion supersedes the open task.
    task_result = await memory.process("Daniel will update the operator documentation by Friday.",
                                       scope=SCOPE, platform="discord", event_id="t1")
    candidate = task_result["candidates"][0]
    assert candidate["assignee"] == "Daniel" and candidate["deadline"].lower() == "friday"
    await memory.process("Operator documentation update is completed.", scope=SCOPE,
                         platform="discord", event_id="t2")
    tasks = await memory.retrieve("operator documentation", SCOPE)
    assert len(tasks) == 1 and tasks[0].task_status == "completed"

    # 3: unresolved blocker is used by a later readiness question.
    await memory.process("Live X verification is still blocked because the required credentials are unavailable.",
                         scope=SCOPE, platform="discord", event_id="b1")
    blocker = await cognition.handle(event("b2", "@Noesis is X integration ready?", mentioned=True), dry_run=False)
    assert "blocker" in blocker.text.lower() and "credentials" in blocker.text.lower()

    # 4: correction supersedes the old release date.
    await memory.process("The release is August 1.", scope=SCOPE, platform="discord", event_id="c1")
    await memory.process("Correction, the release moved to August 15.", scope=SCOPE,
                         platform="discord", event_id="c2")
    dates = await memory.retrieve("release August", SCOPE)
    assert len(dates) == 1 and "August 15" in dates[0].content

    # 5: durable recall survives executor/store restart.
    await memory.shutdown()
    restarted = AutonomousMemoryService(ScopedMemoryStore(path))
    assert await restarted.retrieve("SQLite", SCOPE)

    # 6: exact scope boundaries prevent cross-guild/channel/platform retrieval.
    assert not await restarted.retrieve("SQLite", MemoryScope("discord", guild_id="guild-b",
        channel_id="channel-a", conversation_id="thread-a"))
    assert not await restarted.retrieve("SQLite", MemoryScope("discord", guild_id="guild-a",
        channel_id="channel-b", conversation_id="thread-a"))
    assert not await restarted.retrieve("SQLite", MemoryScope("x", conversation_id="thread-a"))

    # 7: low-value chat is not durable.
    assert not (await restarted.process("lol gm", scope=SCOPE, platform="discord", event_id="low"))["accepted"]

    # 8: secret is rejected and never appears in the database/operator summary.
    secret = await restarted.process("API_TOKEN=extremely-sensitive-value", scope=SCOPE,
                                     platform="discord", event_id="secret")
    assert secret["rejected"][0]["rejection_reason"] == "sensitive_content"
    serialized = str(restarted.store.operator_summary())
    assert "extremely-sensitive-value" not in serialized
    await restarted.shutdown()
