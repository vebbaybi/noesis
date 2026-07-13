from __future__ import annotations

import asyncio
import hashlib
import re
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Literal

from noesis_agent.memory.sqlite_memory import MemoryRecord, MemoryScope, ScopedMemoryStore
from noesis_agent.memory.async_executor import AsyncMemoryExecutor, MemoryQueueFull

CandidateType = Literal["decision", "task", "blocker", "correction", "question", "preference", "fact"]


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    candidate_type: CandidateType
    content: str
    confidence: float
    importance: float
    actionability: float
    source_event_id: str
    stable_id: str
    rejection_reason: str | None = None
    assignee: str | None = None
    deadline: str | None = None
    task_status: str | None = None
    retention_class: str = "project"
    platform: str = "local"
    guild_id: str | None = None
    channel_id: str | None = None
    conversation_id: str | None = None
    user_id: str | None = None
    project_id: str | None = None
    canonical_content: str = ""
    subject: str | None = None
    predicate: str | None = None
    object_value: str | None = None
    category: str = "actionable"
    future_relevance: float = .7
    novelty: float = .8
    stability: float = .8
    source_authority: float = .6
    repetition: float = 0.0
    sensitivity: float = 0.0
    transience: float = .1
    contradiction_risk: float = .1
    spam_probability: float = 0.0
    proposed_expiration: str | None = None
    visibility: str = "conversation"
    provenance: tuple[str, ...] = ()
    extraction_method: str = "deterministic_local"
    storage_explanation: str = "Actionable information with likely future relevance."
    score_breakdown: dict[str, float] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class MemoryDecision:
    candidate_id: str
    status: Literal["persisted", "persisted_temporarily", "merged_existing", "superseded_previous",
                    "rejected_low_value", "rejected_sensitive", "rejected_transient",
                    "rejected_duplicate", "rejected_uncertain", "rejected_unauthorized",
                    "held_unresolved", "requires_human_review", "memory_unavailable"]
    reason: str
    memory_id: str | None = None
    score: float = 0.0


class MemoryWriteGate:
    def __init__(self, *, confidence_threshold: float, importance_threshold: float,
                 actionability_threshold: float) -> None:
        self.confidence_threshold = confidence_threshold
        self.importance_threshold = importance_threshold
        self.actionability_threshold = actionability_threshold

    def evaluate(self, candidate: MemoryCandidate, *, authorized: bool) -> MemoryDecision:
        score = sum(candidate.score_breakdown.values()) if candidate.score_breakdown else (
            candidate.confidence + candidate.importance + candidate.actionability) / 3
        if not authorized:
            return MemoryDecision(candidate.stable_id, "rejected_unauthorized", "authorization_required", score=score)
        if candidate.rejection_reason == "sensitive_content" or candidate.sensitivity >= .5:
            return MemoryDecision(candidate.stable_id, "rejected_sensitive", "sensitive_content", score=score)
        if candidate.transience >= .8:
            return MemoryDecision(candidate.stable_id, "rejected_transient", "transient_fact", score=score)
        if candidate.confidence < self.confidence_threshold:
            return MemoryDecision(candidate.stable_id, "rejected_uncertain", "below_confidence_threshold", score=score)
        if candidate.importance < self.importance_threshold or candidate.actionability < self.actionability_threshold:
            return MemoryDecision(candidate.stable_id, "rejected_low_value", "below_persistence_threshold", score=score)
        return MemoryDecision(candidate.stable_id, "persisted", "write_gate_passed", score=score)


class CandidateExtractor:
    _SECRET = re.compile(r"(?i)(api[_ -]?key|token|password|secret|authorization)\s*[:=]|\b(?:sk-|ghp_|xox[baprs]-)[A-Za-z0-9_-]{8,}")

    def extract(self, text: str, *, platform: str, event_id: str, scope: MemoryScope) -> list[MemoryCandidate]:
        cleaned = " ".join(text.split()).strip()
        if len(cleaned) < 8 or cleaned.lower() in {"lol gm", "gm", "hello", "hi", "thanks"}:
            return []
        kind: CandidateType | None = None
        confidence, importance, actionability = .82, .75, .7
        lower = cleaned.lower()
        if self._SECRET.search(cleaned):
            kind, confidence = "preference", 1.0
            rejection = "sensitive_content"
        else:
            rejection = None
            if re.search(r"\b(correction|actually|moved to|instead|completed|finished|resolved|done)\b", lower):
                kind, importance, actionability = "correction", .95, .9
            elif re.search(r"\b(blocked|blocker|cannot proceed|can't proceed|waiting for)\b", lower):
                kind, importance, actionability = "blocker", .9, .95
            elif re.search(r"\b(agreed|decided|decision|we (?:are|will|won't)|staying with|approved)\b", lower):
                kind, importance, actionability = "decision", .9, .85
            elif re.search(r"\b(will|must|needs? to|assigned|by (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|\w+ \d{1,2}))\b", lower):
                kind, importance, actionability = "task", .85, .95
            elif cleaned.endswith("?") and re.search(r"\b(what|when|where|who|why|how|is|are|can|should)\b", lower):
                kind, importance, actionability = "question", .65, .7
            elif re.search(r"\b(prefer|preference|always use)\b", lower):
                kind = "preference"
            elif re.search(r"\b(release|deadline|launch|milestone)\b.*\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}\b", lower):
                kind, importance, actionability = "fact", .85, .8
        if kind is None:
            return []
        assignee = None
        deadline = None
        task_status = "open" if kind in {"task", "blocker", "question"} else None
        if kind == "task":
            match = re.match(r"@?([A-Za-z][A-Za-z0-9_-]{1,40})\s+will\b", cleaned)
            assignee = match.group(1) if match else None
            due = re.search(r"(?i)\bby\s+((?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow)|(?:[A-Z][a-z]+\s+\d{1,2}))\b", cleaned)
            deadline = due.group(1) if due else None
        if kind == "correction" and re.search(r"(?i)\b(completed|finished|resolved|done)\b", cleaned):
            task_status = "completed"
        identity = "|".join((platform, event_id, kind, cleaned.lower(), scope.guild_id or "", scope.channel_id or "", scope.conversation_id or ""))
        stable_id = hashlib.sha256(identity.encode()).hexdigest()
        positive = {"importance": importance, "actionability": actionability,
                    "future_relevance": .8, "novelty": .8, "confidence": confidence,
                    "source_authority": .6, "project_relevance": .8,
                    "unresolved_state": .8 if task_status == "open" else 0.0,
                    "correction_value": 1.0 if kind == "correction" else 0.0}
        negative = {"sensitivity": 1.0 if rejection else 0.0, "transience": .1,
                    "contradiction_risk": .15, "spam_probability": 0.0,
                    "duplication": 0.0, "uncertainty": 1.0 - confidence}
        return [MemoryCandidate(
            candidate_type=kind, content=cleaned, confidence=confidence, importance=importance,
            actionability=actionability, source_event_id=event_id, stable_id=stable_id,
            rejection_reason=rejection, assignee=assignee, deadline=deadline, task_status=task_status,
            platform=platform, guild_id=scope.guild_id, channel_id=scope.channel_id,
            conversation_id=scope.conversation_id, user_id=scope.user_id, project_id=scope.project_id,
            canonical_content=cleaned, subject=assignee or ("release" if "release" in lower else None),
            predicate=kind, object_value=deadline, sensitivity=1.0 if rejection else 0.0,
            visibility=scope.visibility, provenance=(event_id,),
            score_breakdown={**positive, **{key: -value for key, value in negative.items()}},
        )]


class AutonomousMemoryService:
    def __init__(self, store: ScopedMemoryStore, *, queue_size: int = 128, worker_count: int = 2,
                 timeout: float = 3.0, max_candidates: int = 4,
                 confidence_threshold: float = .7, importance_threshold: float = .7,
                 actionability_threshold: float = .7, extraction_enabled: bool = True) -> None:
        self.store, self.extractor, self.timeout = store, CandidateExtractor(), timeout
        self.executor = AsyncMemoryExecutor(queue_size=queue_size, worker_count=worker_count)
        self.max_candidates = max(1, min(max_candidates, 20))
        self.confidence_threshold = confidence_threshold
        self.importance_threshold = importance_threshold
        self.actionability_threshold = actionability_threshold
        self.extraction_enabled = extraction_enabled
        self.write_gate = MemoryWriteGate(confidence_threshold=confidence_threshold,
                                          importance_threshold=importance_threshold,
                                          actionability_threshold=actionability_threshold)
        self.metrics = {"writes_accepted": 0, "writes_rejected": 0, "retrievals": 0,
                        "moderation_signals": 0, "moderator_alerts": 0,
                        "last_decision": None, "last_safe_error": None, "write_latency_ms": 0.0,
                        "retrieval_latency_ms": 0.0}
        self._recent_moderation: deque[dict] = deque(maxlen=20)

    async def process(self, text: str, *, scope: MemoryScope, platform: str, event_id: str,
                      authorized: bool = True) -> dict:
        candidates = self.extractor.extract(text, platform=platform, event_id=event_id, scope=scope) if self.extraction_enabled else []
        accepted, rejected, decisions = [], [], []
        for candidate in candidates[:self.max_candidates]:
            gate = self.write_gate.evaluate(candidate, authorized=authorized)
            if gate.status != "persisted":
                decisions.append(gate)
                rejected.append({**asdict(candidate), "rejection_reason": gate.reason})
                self.metrics["writes_rejected"] += 1
                continue
            started = time.perf_counter()
            try:
                if await self.executor.run(self.store.source_exists, candidate.stable_id,
                                           timeout=self.timeout):
                    decisions.append(MemoryDecision(candidate.stable_id, "rejected_duplicate",
                                                    "duplicate_event", score=gate.score))
                    rejected.append({**asdict(candidate), "rejection_reason": "duplicate_event"})
                    self.metrics["writes_rejected"] += 1
                    continue
                lookup_types = ("task", "decision", "blocker", "fact") if candidate.candidate_type == "correction" else (candidate.candidate_type,)
                prior = await self.executor.run(self.store.latest_active, scope, types=lookup_types,
                                                timeout=self.timeout)
                if prior:
                    if candidate.candidate_type == "correction":
                        record = await self.executor.run(
                            self.store.correct, prior.memory_id, corrected_content=candidate.content,
                            scope=scope, source_id=candidate.stable_id, timeout=self.timeout)
                    elif self._similar(prior.content, candidate.content) >= .7:
                        record = await self.executor.run(
                            self.store.reinforce, prior.memory_id, scope,
                            confidence=min(1.0, max(prior.confidence, candidate.confidence) + .05),
                            timeout=self.timeout)
                    else:
                        record = await self.executor.run(
                            self.store.remember, content=candidate.content, scope=scope,
                            memory_type=candidate.candidate_type, confidence=candidate.confidence,
                             importance=candidate.importance, actionability=candidate.actionability,
                             task_status=candidate.task_status, retention_class=candidate.retention_class,
                             score_breakdown=candidate.score_breakdown,
                             storage_explanation=candidate.storage_explanation,
                             subject=candidate.subject, predicate=candidate.predicate,
                             object_value=candidate.object_value,
                             source_type="autonomous_event", source_id=candidate.stable_id,
                            timeout=self.timeout)
                else:
                    record = await self.executor.run(
                        self.store.remember, content=candidate.content, scope=scope,
                        memory_type=candidate.candidate_type, confidence=candidate.confidence,
                         importance=candidate.importance, actionability=candidate.actionability,
                         task_status=candidate.task_status, retention_class=candidate.retention_class,
                         score_breakdown=candidate.score_breakdown,
                         storage_explanation=candidate.storage_explanation,
                         subject=candidate.subject, predicate=candidate.predicate,
                         object_value=candidate.object_value,
                         source_type="autonomous_event",
                        source_id=candidate.stable_id, timeout=self.timeout)
                if record:
                    await self.executor.run(self.store.mark_source, candidate.stable_id,
                                            timeout=self.timeout)
                    accepted.append(record)
                    decision_status = "superseded_previous" if candidate.candidate_type == "correction" else \
                                      "merged_existing" if prior and self._similar(prior.content, candidate.content) >= .7 else "persisted"
                    decisions.append(MemoryDecision(candidate.stable_id, decision_status, "write_completed",
                                                    memory_id=record.memory_id, score=gate.score))
                    self.metrics["writes_accepted"] += 1
                else:
                    decisions.append(MemoryDecision(candidate.stable_id, "rejected_duplicate",
                                                    "duplicate_or_write_gate", score=gate.score))
                    rejected.append({**asdict(candidate), "rejection_reason": "duplicate_or_write_gate"})
                    self.metrics["writes_rejected"] += 1
            except MemoryQueueFull:
                decisions.append(MemoryDecision(candidate.stable_id, "memory_unavailable",
                                                "queue_full", score=gate.score))
                self.metrics["last_safe_error"] = "queue_full"
                rejected.append({**asdict(candidate), "rejection_reason": "queue_full"})
                self.metrics["writes_rejected"] += 1
            except Exception as exc:
                decisions.append(MemoryDecision(candidate.stable_id, "memory_unavailable",
                                                "database_error", score=gate.score))
                self.metrics["last_safe_error"] = type(exc).__name__
                rejected.append({**asdict(candidate), "rejection_reason": "memory_unavailable"})
            self.metrics["write_latency_ms"] = round((time.perf_counter()-started)*1000, 2)
        self.metrics["last_decision"] = {"event_id": event_id, "accepted": len(accepted), "rejected": len(rejected)}
        return {"candidates": [asdict(c) for c in candidates], "accepted": accepted,
                "rejected": rejected, "decisions": [asdict(decision) for decision in decisions]}

    async def retrieve(self, query: str, scope: MemoryScope, *, limit: int = 5) -> list[MemoryRecord]:
        started = time.perf_counter()
        records = await self.executor.run(self.store.search, query, scope, limit=limit,
                                          timeout=self.timeout)
        self.metrics["retrievals"] += 1
        self.metrics["retrieval_latency_ms"] = round((time.perf_counter()-started)*1000, 2)
        return records

    def health(self) -> dict:
        return {**self.metrics, **self.executor.health(), "available": self.store.health()["available"],
                "recent_moderation": list(self._recent_moderation)}

    def record_moderation_outcome(self, *, alert: bool, signal: dict | None = None) -> None:
        self.metrics["moderation_signals"] += 1
        if alert:
            self.metrics["moderator_alerts"] += 1
        if signal:
            self._recent_moderation.append({key: signal.get(key) for key in (
                "category", "severity", "confidence", "target_status", "outcome", "safe_summary")})

    async def shutdown(self) -> None:
        await self.executor.shutdown()

    @staticmethod
    def _similar(left: str, right: str) -> float:
        a = set(re.findall(r"[a-z0-9]{3,}", left.lower()))
        b = set(re.findall(r"[a-z0-9]{3,}", right.lower()))
        return len(a & b) / max(1, len(a | b))
