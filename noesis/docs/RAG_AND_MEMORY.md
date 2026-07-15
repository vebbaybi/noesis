# RAG and memory

SQLite/JSON-backed memory remains the structured source of truth. Qdrant is an optional semantic
index. Every query constructs its tenant filter inside the repository adapter; returned payloads are
also checked before crossing the port. The `noesis_memory_v1` collection uses 384-dimensional cosine
vectors from `BAAI/bge-small-en-v1.5`, schema version 1, and indexed tenant/conversation/visibility
payloads. A model or dimension mismatch prevents readiness.

FastEmbed loads lazily once and runs in a bounded executor path. Passage and query embeddings use the
corresponding APIs. Response identities are deterministic UUIDs derived from tenant, event and content
hash. Retrieval content is marked untrusted and length-bounded before model use. Dense retrieval is
implemented; sparse/hybrid retrieval remains deferred.

Recovery is now implemented through `RecoverableMemoryIndex`. Structured source and indexing state
survive vector failures; reconciliation detects and optionally repairs missing/stale points and previews
or explicitly deletes orphans. Model, dimension, content hash, revision and schema mismatches mark a
point stale rather than silently reusing it. See `INDEX_RECOVERY.md`.
