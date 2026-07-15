# Health and readiness

- `/live` proves the API process responds.
- `/ready` evaluates capabilities marked mandatory by configuration and returns HTTP 503 when one is
  disabled, unvalidated, degraded, blocked, or failed.
- `/health` preserves compatibility while including separate liveness, readiness, and capability data.

Capabilities report disabled, initializing, ready, degraded, dependency unavailable, credential
blocked, hardware blocked, platform blocked, failed, or unvalidated. Records include mandatory status,
validation level, last successful/failed checks, failure category and retry state. Adapter construction
alone is `unvalidated`, never `ready`.

Mandatory flags are `NOESIS_LOCAL_LLM_REQUIRED`, `NOESIS_RAG_REQUIRED`,
`NOESIS_MODERATION_STAGE_TWO_REQUIRED`, and `NOESIS_REDIS_REQUIRED`.
