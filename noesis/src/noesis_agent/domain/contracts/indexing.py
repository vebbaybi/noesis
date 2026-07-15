from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class IndexFailure(str, Enum):
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    DIMENSION_MISMATCH = "dimension_mismatch"
    MODEL_MISMATCH = "model_mismatch"
    INTERNAL = "internal"


class SemanticSourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    tenant_id: str
    conversation_id: str
    author_id: str
    text: str = Field(min_length=1, max_length=4000)
    revision: int = Field(default=1, ge=1)
    content_hash: str
    visibility: str = "conversation"
    memory_type: str = "conversation"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IndexingState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    tenant_id: str
    source_revision: int
    content_hash: str
    embedding_model: str
    embedding_dimension: int
    vector_schema_version: int
    last_attempt_at: datetime
    last_success_at: datetime | None = None
    failure_category: IndexFailure | None = None
    retry_count: int = 0
    next_retry_at: datetime | None = None
    point_id: str


class VectorPointMetadata(BaseModel):
    point_id: str
    source_id: str
    tenant_id: str
    revision: int
    content_hash: str
    embedding_model: str
    embedding_dimension: int
    schema_version: int


class ReconciliationReport(BaseModel):
    tenant_id: str | None = None
    source_count: int
    vector_count: int
    missing_source_ids: list[str] = Field(default_factory=list)
    stale_source_ids: list[str] = Field(default_factory=list)
    orphan_point_ids: list[str] = Field(default_factory=list)
    failed_source_ids: list[str] = Field(default_factory=list)
    repaired_source_ids: list[str] = Field(default_factory=list)
    deleted_orphan_ids: list[str] = Field(default_factory=list)


__all__ = [
    "IndexFailure", "IndexingState", "ReconciliationReport", "SemanticSourceRecord",
    "VectorPointMetadata",
]
