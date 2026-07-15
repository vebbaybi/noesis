from __future__ import annotations

import re
import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


MemoryType = Literal["working", "episodic", "semantic", "social", "procedural", "summary", "explicit", "tool_result", "decision", "task", "blocker", "correction", "question", "preference", "fact"]


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
    actionability: float = 0.0
    task_status: str | None = None
    retention_class: str = "project"
    last_retrieved_at: str | None = None
    score_breakdown: dict[str, float] | None = None
    storage_explanation: str = ""
    subject: str | None = None
    predicate: str | None = None
    object_value: str | None = None


class ScopedMemoryStore:
    SCHEMA_VERSION = 3
    _SENSITIVE = re.compile(r"(?i)\b(api[_ -]?key|token|password|secret|authorization)\b")
    _SEARCH_STOP = {"noesis", "this", "that", "what", "when", "where", "which", "who",
                    "why", "how", "does", "have", "with", "version", "right", "current",
                    "remember", "using", "used", "here", "there", "is", "are", "the", "for"}

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.hygiene_actions = 0
        self.hygiene_last_scan: dict[str, object] | None = None
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
                CREATE TABLE IF NOT EXISTS processed_memory_sources(source_id TEXT PRIMARY KEY, processed_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS memories(
                    memory_id TEXT PRIMARY KEY, memory_type TEXT NOT NULL, content TEXT NOT NULL,
                    platform TEXT NOT NULL, guild_id TEXT, channel_id TEXT, conversation_id TEXT,
                    user_id TEXT, project_id TEXT, visibility TEXT NOT NULL,
                    confidence REAL NOT NULL, importance REAL NOT NULL, created_at TEXT NOT NULL,
                    expires_at TEXT, source_type TEXT NOT NULL, source_id TEXT,
                    superseded_by TEXT, deleted_at TEXT,
                    actionability REAL NOT NULL DEFAULT 0,
                    task_status TEXT,
                    retention_class TEXT NOT NULL DEFAULT 'project',
                    last_retrieved_at TEXT,
                    score_breakdown TEXT NOT NULL DEFAULT '{}',
                    storage_explanation TEXT NOT NULL DEFAULT '',
                    subject TEXT,
                    predicate TEXT,
                    object_value TEXT,
                    FOREIGN KEY(superseded_by) REFERENCES memories(memory_id)
                );
                CREATE INDEX IF NOT EXISTS idx_memory_scope ON memories(platform,guild_id,channel_id,conversation_id,user_id);
                CREATE INDEX IF NOT EXISTS idx_memory_active ON memories(deleted_at,expires_at,superseded_by);
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(memories)").fetchall()}
            for name, definition in {
                "actionability": "REAL NOT NULL DEFAULT 0", "task_status": "TEXT",
                "retention_class": "TEXT NOT NULL DEFAULT 'project'", "last_retrieved_at": "TEXT",
                "score_breakdown": "TEXT NOT NULL DEFAULT '{}'", "storage_explanation": "TEXT NOT NULL DEFAULT ''",
                "subject": "TEXT", "predicate": "TEXT", "object_value": "TEXT",
            }.items():
                if name not in columns:
                    db.execute(f"ALTER TABLE memories ADD COLUMN {name} {definition}")
            db.execute("INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES(?,?)",
                       (self.SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()))

    def remember(self, *, content: str, scope: MemoryScope, memory_type: MemoryType = "explicit",
                 confidence: float = 0.8, importance: float = 0.7, source_type: str = "user_explicit",
                 source_id: str | None = None, expires_at: str | None = None,
                 actionability: float = 0.0, task_status: str | None = None,
                 retention_class: str = "project", score_breakdown: dict[str, float] | None = None,
                 storage_explanation: str = "", subject: str | None = None,
                 predicate: str | None = None, object_value: str | None = None) -> MemoryRecord | None:
        text = " ".join(content.split()).strip()
        if len(text) < 4 or self._SENSITIVE.search(text):
            return None
        memory_id = uuid.uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            if source_id and db.execute("SELECT 1 FROM memories WHERE source_id=? AND deleted_at IS NULL", (source_id,)).fetchone():
                return None
            db.execute("""INSERT INTO memories(memory_id,memory_type,content,platform,guild_id,
                channel_id,conversation_id,user_id,project_id,visibility,confidence,importance,
                created_at,expires_at,source_type,source_id,superseded_by,deleted_at,actionability,
                task_status,retention_class,last_retrieved_at,score_breakdown,storage_explanation,
                subject,predicate,object_value)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,?,?,?,NULL,?,?,?,?,?)""", (
                memory_id, memory_type, text, scope.platform, scope.guild_id, scope.channel_id,
                scope.conversation_id, scope.user_id, scope.project_id, scope.visibility,
                confidence, importance, created_at, expires_at, source_type, source_id, None,
                actionability, task_status, retention_class,
                json.dumps(score_breakdown or {}, sort_keys=True), storage_explanation,
                subject, predicate, object_value,
            ))
        return MemoryRecord(memory_id, memory_type, text, scope, confidence, importance, created_at,
                            expires_at, source_type, source_id, None, actionability, task_status,
                            retention_class, None, score_breakdown or {}, storage_explanation,
                            subject, predicate, object_value)

    def search(self, query: str, scope: MemoryScope, *, limit: int = 5) -> list[MemoryRecord]:
        terms = [term for term in re.findall(r"[a-z0-9]{2,}", query.lower())
                 if term not in self._SEARCH_STOP][:12]
        lowered = query.lower()
        topic = "release" if re.search(r"\b(release|launch|milestone|deadline|date)\b", lowered) else \
                "database" if re.search(r"\b(database|mysql|postgres(?:ql)?|sqlite|storage)\b", lowered) else \
                "task" if re.search(r"\b(task|assigned|assignee|done|complete|blocker)\b", lowered) else None
        if topic and topic not in terms:
            terms.append(topic)
        if re.search(r"\bx\b", lowered) and re.search(r"integration|ready|verified|live", lowered):
            terms.extend(term for term in ("verification", "credentials") if term not in terms)
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
        searchable = "LOWER(content || ' ' || COALESCE(subject,'') || ' ' || COALESCE(predicate,'') || ' ' || COALESCE(object_value,''))"
        clauses.append("(" + " OR ".join(f"{searchable} LIKE ?" for _ in terms) + ")")
        values.extend(f"%{term}%" for term in terms)
        values.append(100)
        sql = f"SELECT * FROM memories WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT ?"
        with self._lock, self._connect() as db:
            rows = db.execute(sql, values).fetchall()
            changed = self._downgrade_question_decisions(db, rows)
            if changed:
                self.hygiene_actions += changed
                rows = db.execute(sql, values).fetchall()
            def relevance(row: sqlite3.Row) -> tuple[float, float, str]:
                haystack = " ".join(str(row[key] or "") for key in
                                    ("content", "subject", "predicate", "object_value")).lower()
                matched = sum(1 for term in terms if term in haystack)
                topic_match = 1.0 if topic and (topic in haystack or
                    (topic == "release" and row["subject"] == "release") or
                    (topic == "database" and row["subject"] == "database")) else 0.0
                unresolved_penalty = -.35 if row["memory_type"] == "question" and "?" not in query else 0.0
                return (topic_match * 3 + matched / max(1, len(terms)) + unresolved_penalty,
                        float(row["importance"]), row["created_at"])
            rows = sorted(rows, key=relevance, reverse=True)[:max(1, min(limit, 20))]
            if rows:
                db.executemany("UPDATE memories SET last_retrieved_at=? WHERE memory_id=?",
                               [(datetime.now(timezone.utc).isoformat(), row["memory_id"]) for row in rows])
            return [self._row(row) for row in rows]

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
                                    source_id=source_id,
                                    task_status="completed" if re.search(r"(?i)\b(done|completed|finished|resolved)\b", corrected_content) else None)
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

    def latest_active(self, scope: MemoryScope, *, types: tuple[str, ...]) -> MemoryRecord | None:
        placeholders = ",".join("?" for _ in types)
        with self._lock, self._connect() as db:
            rows = db.execute(f"""SELECT * FROM memories WHERE platform=? AND guild_id IS ?
                AND channel_id IS ? AND conversation_id IS ? AND deleted_at IS NULL
                AND superseded_by IS NULL AND memory_type IN ({placeholders})
                ORDER BY created_at DESC LIMIT 20""",
                (scope.platform, scope.guild_id, scope.channel_id, scope.conversation_id, *types)).fetchall()
            changed = self._downgrade_question_decisions(db, rows)
            self.hygiene_actions += changed
            row = next((item for item in rows if not (
                item["memory_type"] == "decision" and self._question_shaped(item["content"]))), None)
        return self._row(row) if row else None

    def reinforce(self, memory_id: str, scope: MemoryScope, *, confidence: float) -> MemoryRecord | None:
        with self._lock, self._connect() as db:
            db.execute("""UPDATE memories SET confidence=MIN(1.0, MAX(confidence, ?))
                WHERE memory_id=? AND platform=? AND guild_id IS ? AND channel_id IS ?
                AND conversation_id IS ? AND deleted_at IS NULL AND superseded_by IS NULL""",
                (confidence, memory_id, scope.platform, scope.guild_id, scope.channel_id,
                 scope.conversation_id))
            row = db.execute("SELECT * FROM memories WHERE memory_id=?", (memory_id,)).fetchone()
        return self._row(row) if row else None

    def source_exists(self, source_id: str) -> bool:
        with self._lock, self._connect() as db:
            return (db.execute("SELECT 1 FROM processed_memory_sources WHERE source_id=?", (source_id,)).fetchone() is not None
                    or db.execute("SELECT 1 FROM memories WHERE source_id=?", (source_id,)).fetchone() is not None)

    def mark_source(self, source_id: str) -> None:
        with self._lock, self._connect() as db:
            db.execute("INSERT OR IGNORE INTO processed_memory_sources VALUES(?,?)",
                       (source_id, datetime.now(timezone.utc).isoformat()))

    def health(self) -> dict[str, object]:
        with self._lock, self._connect() as db:
            count = db.execute("SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL").fetchone()[0]
            integrity = db.execute("PRAGMA quick_check").fetchone()[0]
        return {"backend": "sqlite", "schema_version": self.SCHEMA_VERSION,
                "available": integrity == "ok", "record_count": count, "lexical_search": True,
                "memory_hygiene_actions": self.hygiene_actions,
                "memory_hygiene": self.memory_diagnostics()}

    def run_hygiene(self) -> dict[str, object]:
        """Scan the real persisted store and downgrade invalid decision-shaped questions."""
        with self._lock, self._connect() as db:
            rows = db.execute("""SELECT * FROM memories WHERE deleted_at IS NULL
                AND superseded_by IS NULL AND memory_type='decision'""").fetchall()
            found = sum(self._question_shaped(row["content"]) for row in rows)
            downgraded = self._downgrade_question_decisions(db, rows)
            self.hygiene_actions += downgraded
        self.hygiene_last_scan = {
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "question_shaped_decisions_found": found,
            "downgraded": downgraded,
        }
        return dict(self.hygiene_last_scan)

    def memory_diagnostics(self) -> dict[str, object]:
        with self._lock, self._connect() as db:
            row = db.execute("""SELECT COUNT(memory_id) AS total,
                SUM(CASE WHEN memory_type='decision' THEN 1 ELSE 0 END) AS decisions,
                SUM(CASE WHEN predicate='legacy_question_downgraded' THEN 1 ELSE 0 END) AS downgraded,
                MAX(created_at) AS last_write FROM memories WHERE deleted_at IS NULL""").fetchone()
            active_decisions = db.execute("""SELECT content FROM memories WHERE deleted_at IS NULL
                AND superseded_by IS NULL AND memory_type='decision'""").fetchall()
        return {
            "database_path": str(self.path.resolve()),
            "total_memory_count": int(row["total"] or 0),
            "decision_memory_count": int(row["decisions"] or 0),
            "question_shaped_decision_count": sum(self._question_shaped(item["content"])
                                                   for item in active_decisions),
            "hygiene_downgraded_count": int(row["downgraded"] or 0),
            "last_memory_write_at": row["last_write"],
            "last_hygiene_scan": self.hygiene_last_scan,
        }

    def operator_summary(self, *, preview_limit: int = 6) -> dict[str, object]:
        """Return bounded, non-sensitive memory statistics for the local operator UI."""
        limit = max(0, min(preview_limit, 20))
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            active = db.execute("""SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL
                AND superseded_by IS NULL AND (expires_at IS NULL OR expires_at>?)""", (now,)).fetchone()[0]
            superseded = db.execute(
                "SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL AND superseded_by IS NOT NULL"
            ).fetchone()[0]
            expired = db.execute(
                "SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL AND expires_at IS NOT NULL AND expires_at<=?",
                (now,),
            ).fetchone()[0]
            deleted = db.execute("SELECT COUNT(*) FROM memories WHERE deleted_at IS NOT NULL").fetchone()[0]
            by_type = {row["memory_type"]: row["count"] for row in db.execute(
                """SELECT memory_type, COUNT(*) AS count FROM memories WHERE deleted_at IS NULL
                AND superseded_by IS NULL AND (expires_at IS NULL OR expires_at>?)
                GROUP BY memory_type ORDER BY count DESC""", (now,)
            ).fetchall()}
            recent = db.execute("""SELECT memory_id, memory_type, content, platform, confidence,
                importance, actionability, retention_class, task_status, source_type, source_id,
                score_breakdown, storage_explanation, created_at FROM memories
                WHERE deleted_at IS NULL AND superseded_by IS NULL
                AND (expires_at IS NULL OR expires_at>?) ORDER BY created_at DESC LIMIT ?""",
                (now, limit)).fetchall()
        return {
            "active": active, "superseded": superseded, "expired": expired, "deleted": deleted,
            "by_type": by_type,
            "memory_hygiene_actions": self.hygiene_actions,
            "recent": [{
                "id": row["memory_id"][:8], "type": row["memory_type"],
                "summary": self._safe_preview(row["content"]), "platform": row["platform"],
                "confidence": round(float(row["confidence"]), 2),
                "importance": round(float(row["importance"]), 2),
                "actionability": round(float(row["actionability"]), 2),
                "retention_class": row["retention_class"], "task_status": row["task_status"],
                "provenance": {"source_type": row["source_type"],
                               "source_id": row["source_id"][:12] if row["source_id"] else None},
                "score_breakdown": json.loads(row["score_breakdown"] or "{}"),
                "storage_explanation": row["storage_explanation"],
                "created_at": row["created_at"],
            } for row in recent],
        }

    @classmethod
    def _safe_preview(cls, content: str, limit: int = 120) -> str:
        if cls._SENSITIVE.search(content):
            return "Sensitive memory hidden"
        cleaned = " ".join(content.split())
        return cleaned if len(cleaned) <= limit else cleaned[:limit - 1].rstrip() + "…"

    @staticmethod
    def _row(row: sqlite3.Row) -> MemoryRecord:
        scope = MemoryScope(row["platform"], row["guild_id"], row["channel_id"],
                            row["conversation_id"], row["user_id"], row["project_id"], row["visibility"])
        return MemoryRecord(row["memory_id"], row["memory_type"], row["content"], scope,
                            row["confidence"], row["importance"], row["created_at"], row["expires_at"],
                            row["source_type"], row["source_id"], row["superseded_by"],
                            row["actionability"], row["task_status"], row["retention_class"],
                            row["last_retrieved_at"], json.loads(row["score_breakdown"] or "{}"),
                            row["storage_explanation"], row["subject"], row["predicate"],
                            row["object_value"])

    @staticmethod
    def _question_shaped(content: str) -> bool:
        value = " ".join(str(content or "").lower().split())
        return ("?" in value or bool(re.search(
            r"(?:\b(?:is|are|do|does|did|can|could|should|would|will)\s+(?:we|it|this|that)\b|"
            r"\b(?:right|correct)\s*[?.!]*$|^@?noesis\b.*\b(?:is|are|can|should|do)\b)", value)))

    def _downgrade_question_decisions(self, db: sqlite3.Connection, rows) -> int:
        corrupt = [row for row in rows if row["memory_type"] == "decision" and
                   self._question_shaped(row["content"])]
        for row in corrupt:
            explanation = "Legacy question-shaped decision downgraded to open question; provenance preserved."
            db.execute("""UPDATE memories SET memory_type='question', task_status='open',
                predicate='legacy_question_downgraded', storage_explanation=? WHERE memory_id=?""",
                       (explanation, row["memory_id"]))
        return len(corrupt)


__all__ = ["MemoryRecord", "MemoryScope", "ScopedMemoryStore"]
