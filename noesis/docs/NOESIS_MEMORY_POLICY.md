# Memory Policy

Durable scoped memory uses `data/memory/noesis_memory.sqlite3`. Operator responses expose only backend health/counts, never the path or memory contents.

Every record carries platform, guild/workspace, channel, conversation/thread, user, project, visibility, type, confidence, importance, source, timestamps, expiry, and supersession state. Retrieval filters scope before lexical ranking. Exact records cannot cross platform, guild, channel, thread, or user boundaries.

The write gate rejects empty/low-value text and obvious credential-bearing content. Explicit writes, corrections, expiration, deletion, and restart persistence are implemented. Deleted/expired/superseded records are excluded. Embeddings, encryption-at-rest, automatic transcript migration, backup UI, and operator mutation controls are not implemented.

Raw platform messages are not automatically written to this store or used for training. Future writes require explicit policy, sensitivity checks, retention, provenance, and an asynchronous runtime boundary.
