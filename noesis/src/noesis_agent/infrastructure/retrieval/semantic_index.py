from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import NAMESPACE_URL, UUID, uuid5

if TYPE_CHECKING:
    from qdrant_client import AsyncQdrantClient

from noesis_agent.domain.contracts.intelligence import (
    CapabilityHealth, CapabilityState, IntelligenceRequest, RetrievalItem,
)
from noesis_agent.domain.contracts.indexing import SemanticSourceRecord, VectorPointMetadata


@dataclass(frozen=True, slots=True)
class IndexConfig:
    url: str
    collection: str = "noesis_memory_v1"
    model: str = "BAAI/bge-small-en-v1.5"
    dimension: int = 384
    timeout_seconds: float = 3.0
    schema_version: int = 1


class SemanticIndex:
    """Qdrant index with mandatory tenant filters and managed FastEmbed workers."""

    def __init__(self, config: IndexConfig, *, enabled: bool = False, concurrency: int = 2) -> None:
        self._config = config
        self._enabled = enabled
        self._slots = asyncio.Semaphore(concurrency)
        self._client: AsyncQdrantClient | None = None
        self._embedder: object | None = None
        self._ready = False
        self._failure = ""

    async def initialize(self) -> None:
        if not self._enabled:
            return
        if importlib.util.find_spec("qdrant_client") is None or importlib.util.find_spec("fastembed") is None:
            self._failure = "Install noesis-agent[rag] to enable semantic retrieval."
            return
        from qdrant_client import AsyncQdrantClient, models
        self._client = AsyncQdrantClient(
            location=":memory:" if self._config.url == ":memory:" else None,
            url=None if self._config.url == ":memory:" else self._config.url,
            timeout=math.ceil(self._config.timeout_seconds),
        )
        collections = await self._client.get_collections()
        names = {item.name for item in collections.collections}
        if self._config.collection not in names:
            await self._client.create_collection(
                collection_name=self._config.collection,
                vectors_config=models.VectorParams(size=self._config.dimension, distance=models.Distance.COSINE),
            )
            for field in ("tenant_id", "conversation_id", "memory_type", "visibility"):
                await self._client.create_payload_index(
                    collection_name=self._config.collection, field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
        else:
            info = await self._client.get_collection(self._config.collection)
            vectors = info.config.params.vectors
            size = getattr(vectors, "size", None)
            if size != self._config.dimension:
                raise ValueError(f"Qdrant collection dimension {size} != configured {self._config.dimension}")
        self._ready = True

    async def _embedding(self, text: str, *, query: bool) -> list[float]:
        async with self._slots:
            return await asyncio.get_running_loop().run_in_executor(None, self._embedding_sync, text, query)

    def _embedding_sync(self, text: str, query: bool) -> list[float]:
        if self._embedder is None:
            from fastembed import TextEmbedding
            models = {item["model"]: item for item in TextEmbedding.list_supported_models()}
            if self._config.model not in models:
                raise ValueError(f"FastEmbed model is not supported: {self._config.model}")
            if int(models[self._config.model]["dim"]) != self._config.dimension:
                raise ValueError("Configured embedding dimension does not match FastEmbed metadata")
            self._embedder = TextEmbedding(model_name=self._config.model)
        method = self._embedder.query_embed if query else self._embedder.passage_embed  # type: ignore[attr-defined]
        vector = next(iter(method([text])))
        return [float(value) for value in vector]

    async def retrieve(self, request: IntelligenceRequest, *, limit: int) -> list[RetrievalItem]:
        if not self._ready or self._client is None:
            return []
        from qdrant_client import models
        vector = await self._embedding(request.text, query=True)
        tenant_filter = models.Filter(must=[
            models.FieldCondition(key="tenant_id", match=models.MatchValue(value=request.tenant_id)),
            models.FieldCondition(key="visibility", match=models.MatchAny(any=["tenant", "conversation"])),
        ])
        response = await self._client.query_points(
            collection_name=self._config.collection, query=vector, query_filter=tenant_filter,
            limit=min(limit, 20), score_threshold=0.25, with_payload=True,
        )
        return [RetrievalItem(
            point_id=str(point.id), tenant_id=str(point.payload["tenant_id"]),
            text=str(point.payload["text"])[:4000], score=max(0.0, min(1.0, float(point.score))),
            source_id=str(point.payload["source_id"]), provenance=str(point.payload["source_type"]),
        ) for point in response.points if point.payload and point.payload.get("tenant_id") == request.tenant_id]

    async def remember(self, request: IntelligenceRequest, text: str) -> None:
        if not self._ready or self._client is None:
            return
        from qdrant_client import models
        digest = hashlib.sha256(text.encode()).hexdigest()
        point_id = str(uuid5(NAMESPACE_URL, f"{request.tenant_id}:{request.event_id}:response:{digest}"))
        payload = {
            "tenant_id": request.tenant_id, "conversation_id": request.conversation_id,
            "source_type": "assistant_response", "source_id": request.event_id,
            "author_id": hashlib.sha256(request.user_id.encode()).hexdigest()[:24],
            "timestamp": datetime.now(timezone.utc).isoformat(), "content_hash": digest,
            "chunk_index": 0, "revision": 1, "visibility": "conversation",
            "memory_type": "conversation", "redaction_status": "reviewed",
            "retention_state": "active", "embedding_model": self._config.model,
            "schema_version": self._config.schema_version, "text": text[:4000],
        }
        vector = await self._embedding(text, query=False)
        await self._client.upsert(collection_name=self._config.collection,
                                  points=[models.PointStruct(id=point_id, vector=vector, payload=payload)], wait=True)

    async def upsert_source(self, record: SemanticSourceRecord) -> str:
        if not self._ready or self._client is None:
            raise ConnectionError("Qdrant semantic index is not ready")
        from qdrant_client import models
        point_id = str(uuid5(NAMESPACE_URL, f"{record.tenant_id}:{record.source_id}"))
        payload = {
            "tenant_id": record.tenant_id, "conversation_id": record.conversation_id,
            "source_type": "structured_memory", "source_id": record.source_id,
            "author_id": record.author_id, "timestamp": record.created_at.isoformat(),
            "content_hash": record.content_hash, "chunk_index": 0, "revision": record.revision,
            "visibility": record.visibility, "memory_type": record.memory_type,
            "redaction_status": "reviewed", "retention_state": "active",
            "embedding_model": self._config.model, "embedding_dimension": self._config.dimension,
            "schema_version": self._config.schema_version, "text": record.text,
        }
        vector = await self._embedding(record.text, query=False)
        if len(vector) != self._config.dimension:
            raise ValueError(f"Embedding dimension {len(vector)} != configured {self._config.dimension}")
        await self._client.upsert(
            collection_name=self._config.collection,
            points=[models.PointStruct(id=point_id, vector=vector, payload=payload)], wait=True,
        )
        return point_id

    async def list_metadata(self, tenant_id: str | None = None) -> list[VectorPointMetadata]:
        if not self._ready or self._client is None:
            return []
        from qdrant_client import models
        query_filter = None if tenant_id is None else models.Filter(must=[
            models.FieldCondition(key="tenant_id", match=models.MatchValue(value=tenant_id))
        ])
        records: list[VectorPointMetadata] = []
        offset: int | str | UUID | None = None
        while True:
            points, offset = await self._client.scroll(
                collection_name=self._config.collection, scroll_filter=query_filter,
                limit=256, offset=offset, with_payload=True, with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                if "source_id" not in payload:
                    continue
                records.append(VectorPointMetadata(
                    point_id=str(point.id), source_id=str(payload["source_id"]),
                    tenant_id=str(payload.get("tenant_id", "")), revision=int(payload.get("revision", 0)),
                    content_hash=str(payload.get("content_hash", "")),
                    embedding_model=str(payload.get("embedding_model", "")),
                    embedding_dimension=int(payload.get("embedding_dimension", self._config.dimension)),
                    schema_version=int(payload.get("schema_version", 0)),
                ))
            if offset is None:
                break
        return records

    async def delete_points(self, point_ids: Sequence[str]) -> None:
        if not point_ids:
            return
        if not self._ready or self._client is None:
            raise ConnectionError("Qdrant semantic index is not ready")
        from qdrant_client import models
        await self._client.delete(
            collection_name=self._config.collection,
            points_selector=models.PointIdsList(points=list(point_ids)), wait=True,
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()

    def health(self) -> CapabilityHealth:
        if not self._enabled:
            return CapabilityHealth(name="rag", state=CapabilityState.DISABLED)
        if self._failure:
            return CapabilityHealth(name="rag", state=CapabilityState.UNAVAILABLE, detail=self._failure)
        return CapabilityHealth(name="rag", state=CapabilityState.READY if self._ready else CapabilityState.LOADING)
