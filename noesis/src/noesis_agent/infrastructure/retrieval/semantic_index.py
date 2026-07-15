from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import NAMESPACE_URL, uuid5

if TYPE_CHECKING:
    from qdrant_client import AsyncQdrantClient

from noesis_agent.domain.contracts.intelligence import (
    CapabilityHealth, CapabilityState, IntelligenceRequest, RetrievalItem,
)


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

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()

    def health(self) -> CapabilityHealth:
        if not self._enabled:
            return CapabilityHealth(name="rag", state=CapabilityState.DISABLED)
        if self._failure:
            return CapabilityHealth(name="rag", state=CapabilityState.UNAVAILABLE, detail=self._failure)
        return CapabilityHealth(name="rag", state=CapabilityState.READY if self._ready else CapabilityState.LOADING)
