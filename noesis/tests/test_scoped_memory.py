from datetime import datetime, timedelta, timezone

from noesis_agent.memory.sqlite_memory import MemoryScope, ScopedMemoryStore


def scope(**changes):
    values = dict(platform="discord", guild_id="g1", channel_id="c1",
                  conversation_id="t1", user_id="u1")
    values.update(changes)
    return MemoryScope(**values)


def test_memory_persists_and_lexical_search_works_without_embeddings(tmp_path) -> None:
    path = tmp_path / "memory.sqlite3"
    store = ScopedMemoryStore(path)
    record = store.remember(content="Project Aurora deploys on Friday", scope=scope())
    assert record is not None
    reopened = ScopedMemoryStore(path)
    assert [item.content for item in reopened.search("Aurora Friday", scope())] == [record.content]
    assert reopened.health()["available"] is True


def test_memory_scope_never_leaks_across_boundaries(tmp_path) -> None:
    store = ScopedMemoryStore(tmp_path / "memory.sqlite3")
    store.remember(content="Scoped launch phrase aurora", scope=scope())
    for other in (
        scope(platform="x"), scope(guild_id="g2"), scope(channel_id="c2"),
        scope(conversation_id="t2"), scope(user_id="u2"),
    ):
        assert store.search("aurora", other) == []


def test_sensitive_low_value_expired_deleted_and_corrected_memory(tmp_path) -> None:
    store = ScopedMemoryStore(tmp_path / "memory.sqlite3")
    assert store.remember(content="hi", scope=scope()) is None
    assert store.remember(content="api token secret value", scope=scope()) is None
    expired = store.remember(content="Old release was Monday", scope=scope(),
        expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    assert expired and store.search("release Monday", scope()) == []
    original = store.remember(content="Release is Tuesday", scope=scope())
    corrected = store.correct(original.memory_id, corrected_content="Release is Wednesday", scope=scope())
    assert corrected
    assert [item.content for item in store.search("Release", scope())] == ["Release is Wednesday"]
    assert store.forget(corrected.memory_id, scope())
    assert store.search("Wednesday", scope()) == []
