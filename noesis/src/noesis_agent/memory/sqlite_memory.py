from __future__ import annotations

import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


MemoryType = Literal["working", "episodic", "semantic", "social", "procedural", "summary", "explicit", "tool_result"]


@dataclass(frozen=True, slots=True)
class MemoryScope:
    platform: str
    guild_id: str | None = None
    channel_id: str | None = None
    conversation_id: str | None = None
    user_id: str | None = None
    project_id: str | None = None
    visibility: str = "conversation"


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    memory_id: str
    memory_type: str
    content: str
    scope: MemoryScope
    confidence: float
    importance: float
    created_at: str
    expires_at: str | None
    source_type: str
    source_id: str | None
    superseded_by: str | None


class ScopedMemoryStore:
    SCHEMA_VERSION = 1
    _SENSITIVE = re.compile(r"(?i)\b(api[_ -]?key|token|password|secret|authorization)\b")

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS memories(
                    memory_id TEXT PRIMARY KEY, memory_type TEXT NOT NULL, content TEXT NOT NULL,
                    platform TEXT NOT NULL, guild_id TEXT, channel_id TEXT, conversation_id TEXT,
                    user_id TEXT, project_id TEXT, visibility TEXT NOT NULL,
                    confidence REAL NOT NULL, importance REAL NOT NULL, created_at TEXT NOT NULL,
                    expires_at TEXT, source_type TEXT NOT NULL, source_id TEXT,
                    superseded_by TEXT, deleted_at TEXT,
                    FOREIGN KEY(superseded_by) REFERENCES memories(memory_id)
                );
                CREATE INDEX IF NOT EXISTS idx_memory_scope ON memories(platform,guild_id,channel_id,conversation_id,user_id);
                CREATE INDEX IF NOT EXISTS idx_memory_active ON memories(deleted_at,expires_at,superseded_by);
            """)
            db.execute("INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES(?,?)",
                       (self.SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()))

    def remember(self, *, content: str, scope: MemoryScope, memory_type: MemoryType = "explicit",
                 confidence: float = 0.8, importance: float = 0.7, source_type: str = "user_explicit",
                 source_id: str | None = None, expires_at: str | None = None) -> MemoryRecord | None:
        text = " ".join(content.split()).strip()
        if len(text) < 4 or self._SENSITIVE.search(text):
            return None
        memory_id = uuid.uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            db.execute("""INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)""", (
                memory_id, memory_type, text, scope.platform, scope.guild_id, scope.channel_id,
                scope.conversation_id, scope.user_id, scope.project_id, scope.visibility,
                confidence, importance, created_at, expires_at, source_type, source_id, None,
            ))
        return MemoryRecord(memory_id, memory_type, text, scope, confidence, importance, created_at,
                            expires_at, source_type, source_id, None)

    def search(self, query: str, scope: MemoryScope, *, limit: int = 5) -> list[MemoryRecord]:
        terms = [term for term in re.findall(r"[a-z0-9]{2,}", query.lower())][:8]
        if not terms:
            return []
        clauses = ["platform=?", "deleted_at IS NULL", "superseded_by IS NULL",
                   "(expires_at IS NULL OR expires_at>?)"]
        values: list[object] = [scope.platform, datetime.now(timezone.utc).isoformat()]
        for column, value in (("guild_id", scope.guild_id), ("channel_id", scope.channel_id),
                              ("conversation_id", scope.conversation_id), ("user_id", scope.user_id)):
            if value is not None:
                clauses.append(f"({column}=? OR {column} IS NULL)")
                values.append(value)
            else:
                clauses.append(f"{column} IS NULL")
        clauses.append("(" + " OR ".join("LOWER(content) LIKE ?" for _ in terms) + ")")
        values.extend(f"%{term}%" for term in terms)
        values.append(max(1, min(limit, 20)))
        sql = f"SELECT * FROM memories WHERE {' AND '.join(clauses)} ORDER BY importance DESC, created_at DESC LIMIT ?"
        with self._lock, self._connect() as db:
            return [self._row(row) for row in db.execute(sql, values).fetchall()]

    def forget(self, memory_id: str, scope: MemoryScope) -> bool:
        with self._lock, self._connect() as db:
            result = db.execute("""UPDATE memories SET deleted_at=? WHERE memory_id=? AND platform=?
                AND guild_id IS ? AND channel_id IS ? AND conversation_id IS ? AND user_id IS ?""",
                (datetime.now(timezone.utc).isoformat(), memory_id, scope.platform, scope.guild_id,
                 scope.channel_id, scope.conversation_id, scope.user_id))
            return result.rowcount == 1

    def correct(self, memory_id: str, *, corrected_content: str, scope: MemoryScope,
                source_id: str | None = None) -> MemoryRecord | None:
        replacement = self.remember(content=corrected_content, scope=scope, memory_type="explicit",
                                    confidence=0.9, importance=0.9, source_type="user_correction",
                                    source_id=source_id)
        if replacement is None:
            return None
        with self._lock, self._connect() as db:
            result = db.execute("""UPDATE memories SET superseded_by=? WHERE memory_id=? AND platform=?
                AND guild_id IS ? AND channel_id IS ? AND conversation_id IS ? AND user_id IS ?
                AND deleted_at IS NULL""", (replacement.memory_id, memory_id, scope.platform, scope.guild_id,
                                            scope.channel_id, scope.conversation_id, scope.user_id))
            if result.rowcount != 1:
                db.execute("UPDATE memories SET deleted_at=? WHERE memory_id=?",
                           (datetime.now(timezone.utc).isoformat(), replacement.memory_id))
                return None
        return replacement

    def health(self) -> dict[str, object]:
        with self._lock, self._connect() as db:
            count = db.execute("SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL").fetchone()[0]
            integrity = db.execute("PRAGMA quick_check").fetchone()[0]
        return {"backend": "sqlite", "schema_version": self.SCHEMA_VERSION,
                "available": integrity == "ok", "record_count": count, "lexical_search": True}

    @staticmethod
    def _row(row: sqlite3.Row) -> MemoryRecord:
        scope = MemoryScope(row["platform"], row["guild_id"], row["channel_id"],
                            row["conversation_id"], row["user_id"], row["project_id"], row["visibility"])
        return MemoryRecord(row["memory_id"], row["memory_type"], row["content"], scope,
                            row["confidence"], row["importance"], row["created_at"], row["expires_at"],
                            row["source_type"], row["source_id"], row["superseded_by"])


__all__ = ["MemoryRecord", "MemoryScope", "ScopedMemoryStore"]
