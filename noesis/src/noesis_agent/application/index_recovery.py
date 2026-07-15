from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from noesis_agent.application.intelligence.ports import RetrievalPort
from noesis_agent.domain.contracts.indexing import (
    IndexFailure, IndexingState, ReconciliationReport, SemanticSourceRecord, VectorPointMetadata,
)
from noesis_agent.domain.contracts.intelligence import CapabilityHealth, IntelligenceRequest, RetrievalItem


class SourceRepository(Protocol):
    def save_source(self, record: SemanticSourceRecord) -> None: ...
    def get_source(self, source_id: str) -> SemanticSourceRecord | None: ...
    def list_sources(self, tenant_id: str | None = None) -> list[SemanticSourceRecord]: ...
    def save_state(self, state: IndexingState) -> None: ...
    def get_state(self, source_id: str) -> IndexingState | None: ...
    def failed_states(self, tenant_id: str | None = None) -> list[IndexingState]: ...


class VectorIndex(Protocol):
    async def retrieve(self, request: IntelligenceRequest, *, limit: int) -> list[RetrievalItem]: ...
    async def upsert_source(self, record: SemanticSourceRecord) -> str: ...
    async def list_metadata(self, tenant_id: str | None = None) -> list[VectorPointMetadata]: ...
    async def delete_points(self, point_ids: Sequence[str]) -> None: ...
    def health(self) -> CapabilityHealth: ...


class RecoverableMemoryIndex(RetrievalPort):
    def __init__(self, source: SourceRepository, vector: VectorIndex, *, embedding_model: str,
                 embedding_dimension: int, schema_version: int = 1) -> None:
        self._source = source
        self._vector = vector
        self._model = embedding_model
        self._dimension = embedding_dimension
        self._schema_version = schema_version

    async def retrieve(self, request: IntelligenceRequest, *, limit: int) -> list[RetrievalItem]:
        return await self._vector.retrieve(request, limit=limit)

    async def remember(self, request: IntelligenceRequest, text: str) -> None:
        digest = hashlib.sha256(text.encode()).hexdigest()
        source_id = str(uuid5(NAMESPACE_URL, f"{request.tenant_id}:{request.event_id}:response"))
        current = self._source.get_source(source_id)
        revision = 1 if current is None else current.revision + (current.content_hash != digest)
        record = SemanticSourceRecord(
            source_id=source_id, tenant_id=request.tenant_id, conversation_id=request.conversation_id,
            author_id=hashlib.sha256(request.user_id.encode()).hexdigest()[:24], text=text,
            revision=revision, content_hash=digest,
        )
        self._source.save_source(record)
        await self._index(record)

    async def _index(self, record: SemanticSourceRecord) -> bool:
        now = datetime.now(timezone.utc)
        previous = self._source.get_state(record.source_id)
        point_id = str(uuid5(NAMESPACE_URL, f"{record.tenant_id}:{record.source_id}"))
        try:
            point_id = await self._vector.upsert_source(record)
        except TimeoutError:
            failure = IndexFailure.TIMEOUT
        except (ConnectionError, OSError):
            failure = IndexFailure.CONNECTION
        except ValueError as exc:
            failure = IndexFailure.DIMENSION_MISMATCH if "dimension" in str(exc).lower() else IndexFailure.MODEL_MISMATCH
        else:
            self._source.save_state(IndexingState(
                source_id=record.source_id, tenant_id=record.tenant_id, source_revision=record.revision,
                content_hash=record.content_hash, embedding_model=self._model,
                embedding_dimension=self._dimension, vector_schema_version=self._schema_version,
                last_attempt_at=now, last_success_at=now, point_id=point_id,
            ))
            return True
        retry_count = (previous.retry_count if previous else 0) + 1
        self._source.save_state(IndexingState(
            source_id=record.source_id, tenant_id=record.tenant_id, source_revision=record.revision,
            content_hash=record.content_hash, embedding_model=self._model,
            embedding_dimension=self._dimension, vector_schema_version=self._schema_version,
            last_attempt_at=now, failure_category=failure, retry_count=retry_count,
            next_retry_at=now + timedelta(seconds=min(3600, 2 ** min(retry_count, 10))), point_id=point_id,
        ))
        return False

    async def reconcile(self, tenant_id: str | None = None, *, repair: bool = False,
                        delete_orphans: bool = False) -> ReconciliationReport:
        sources = self._source.list_sources(tenant_id)
        points = await self._vector.list_metadata(tenant_id)
        source_by_id = {item.source_id: item for item in sources}
        point_by_source = {item.source_id: item for item in points}
        missing = sorted(set(source_by_id) - set(point_by_source))
        stale = sorted(source_id for source_id in set(source_by_id) & set(point_by_source)
                       if self._stale(source_by_id[source_id], point_by_source[source_id]))
        orphans = sorted(item.point_id for item in points if item.source_id not in source_by_id)
        repaired: list[str] = []
        if repair:
            for source_id in [*missing, *stale]:
                if await self._index(source_by_id[source_id]):
                    repaired.append(source_id)
        deleted: list[str] = []
        if delete_orphans and orphans:
            await self._vector.delete_points(orphans)
            deleted = orphans
        return ReconciliationReport(
            tenant_id=tenant_id, source_count=len(sources), vector_count=len(points),
            missing_source_ids=missing, stale_source_ids=stale, orphan_point_ids=orphans,
            failed_source_ids=[item.source_id for item in self._source.failed_states(tenant_id)],
            repaired_source_ids=repaired, deleted_orphan_ids=deleted,
        )

    def _stale(self, source: SemanticSourceRecord, point: VectorPointMetadata) -> bool:
        return point.revision != source.revision or point.content_hash != source.content_hash or \
            point.embedding_model != self._model or point.embedding_dimension != self._dimension or \
            point.schema_version != self._schema_version

    def health(self) -> CapabilityHealth:
        return self._vector.health()
