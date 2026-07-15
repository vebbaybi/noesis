# Semantic-index recovery

JSON structured records are authoritative; Qdrant is derived. Every semantic source has persisted
revision, hash, tenant, model, dimension, schema, attempt, success, failure, retry, and point state.
Reconciliation detects missing points, stale revisions/configuration, failed records, and orphans.

Preview is read-only. Repair re-indexes missing/stale records. Orphan deletion is separate and requires
explicit operator confirmation. A structured write survives Qdrant failure and records exponential
retry state. Qdrant success never substitutes for the structured record.

Local operator routes:

- `GET /operator/index/reconciliation`
- `POST /operator/index/reconciliation` with `confirm=true` for mutations

The in-memory Qdrant integration test proves round-trip and reconciliation without production data.
