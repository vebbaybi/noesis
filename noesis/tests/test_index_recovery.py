from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from noesis_agent.application.index_recovery import RecoverableMemoryIndex
from noesis_agent.domain.contracts.indexing import SemanticSourceRecord, VectorPointMetadata
from noesis_agent.domain.contracts.intelligence import CapabilityHealth, CapabilityState, IntelligenceRequest
from noesis_agent.infrastructure.persistence.index_store import JsonSemanticSourceRepository
from noesis_agent.infrastructure.persistence.json_store import JsonStore


class _Vector:
    def __init__(self) -> None:
        self.points: dict[str, VectorPointMetadata] = {}
        self.fail = False

    async def retrieve(self, request: IntelligenceRequest, *, limit: int):
        return []

    async def upsert_source(self, record: SemanticSourceRecord) -> str:
        if self.fail:
            raise ConnectionError("qdrant unavailable")
        point_id = f"point:{record.source_id}"
        self.points[point_id] = VectorPointMetadata(
            point_id=point_id, source_id=record.source_id, tenant_id=record.tenant_id,
            revision=record.revision, content_hash=record.content_hash,
            embedding_model="BAAI/bge-small-en-v1.5", embedding_dimension=384, schema_version=1,
        )
        return point_id

    async def list_metadata(self, tenant_id: str | None = None) -> list[VectorPointMetadata]:
        return [item for item in self.points.values() if tenant_id is None or item.tenant_id == tenant_id]

    async def delete_points(self, point_ids):
        for point_id in point_ids:
            self.points.pop(point_id, None)

    def health(self) -> CapabilityHealth:
        return CapabilityHealth(name="rag", state=CapabilityState.READY)


def _source(source_id: str, tenant: str = "tenant-a", revision: int = 1,
            text: str = "memory") -> SemanticSourceRecord:
    return SemanticSourceRecord(
        source_id=source_id, tenant_id=tenant, conversation_id="c", author_id="u", text=text,
        revision=revision, content_hash=hashlib.sha256(text.encode()).hexdigest(),
    )


@pytest.mark.asyncio
async def test_reconciliation_recovers_missing_and_stale_points_and_cleans_orphans(tmp_path: Path) -> None:
    repository = JsonSemanticSourceRepository(JsonStore(tmp_path))
    vector = _Vector()
    recovery = RecoverableMemoryIndex(repository, vector,
                                      embedding_model="BAAI/bge-small-en-v1.5", embedding_dimension=384)
    missing = _source("missing")
    stale = _source("stale", revision=2, text="new revision")
    repository.save_source(missing)
    repository.save_source(stale)
    vector.points["point:stale"] = VectorPointMetadata(
        point_id="point:stale", source_id="stale", tenant_id="tenant-a", revision=1,
        content_hash="old", embedding_model="BAAI/bge-small-en-v1.5",
        embedding_dimension=384, schema_version=1,
    )
    vector.points["orphan"] = VectorPointMetadata(
        point_id="orphan", source_id="deleted", tenant_id="tenant-a", revision=1,
        content_hash="gone", embedding_model="BAAI/bge-small-en-v1.5",
        embedding_dimension=384, schema_version=1,
    )
    preview = await recovery.reconcile("tenant-a")
    assert preview.missing_source_ids == ["missing"]
    assert preview.stale_source_ids == ["stale"]
    assert preview.orphan_point_ids == ["orphan"]
    repaired = await recovery.reconcile("tenant-a", repair=True, delete_orphans=True)
    assert repaired.repaired_source_ids == ["missing", "stale"]
    assert repaired.deleted_orphan_ids == ["orphan"]
    clean = await recovery.reconcile("tenant-a")
    assert not clean.missing_source_ids and not clean.stale_source_ids and not clean.orphan_point_ids


@pytest.mark.asyncio
async def test_structured_record_survives_qdrant_failure_and_retry(tmp_path: Path) -> None:
    repository = JsonSemanticSourceRepository(JsonStore(tmp_path))
    vector = _Vector()
    vector.fail = True
    recovery = RecoverableMemoryIndex(repository, vector,
                                      embedding_model="BAAI/bge-small-en-v1.5", embedding_dimension=384)
    request = IntelligenceRequest(event_id="e", tenant_id="tenant-a", user_id="u",
                                  conversation_id="c", text="remember")
    await recovery.remember(request, "durable structured memory")
    assert len(repository.list_sources("tenant-a")) == 1
    assert len(repository.failed_states("tenant-a")) == 1
    vector.fail = False
    report = await recovery.reconcile("tenant-a", repair=True)
    assert len(report.repaired_source_ids) == 1


@pytest.mark.asyncio
async def test_real_in_memory_qdrant_reconciliation_round_trip(tmp_path: Path) -> None:
    pytest.importorskip("fastembed")
    pytest.importorskip("qdrant_client")
    from noesis_agent.infrastructure.retrieval.semantic_index import IndexConfig, SemanticIndex

    repository = JsonSemanticSourceRepository(JsonStore(tmp_path))
    vector = SemanticIndex(IndexConfig(url=":memory:"), enabled=True)
    await vector.initialize()
    recovery = RecoverableMemoryIndex(repository, vector,
                                      embedding_model="BAAI/bge-small-en-v1.5", embedding_dimension=384)
    request = IntelligenceRequest(event_id="real", tenant_id="tenant-a", user_id="u",
                                  conversation_id="c", text="Noesis recovery")
    await recovery.remember(request, "Noesis recovery uses its structured source of truth.")
    report = await recovery.reconcile("tenant-a")
    assert report.source_count == report.vector_count == 1
    assert not report.missing_source_ids and not report.stale_source_ids
    await vector.close()
