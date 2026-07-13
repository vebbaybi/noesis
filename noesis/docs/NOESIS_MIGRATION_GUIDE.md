# Migration Guide

SQLite scoped memory initializes schema version 1 idempotently on first `MemoryService` construction. Existing JSON episodic/session memory is preserved and remains readable through existing services; it is not automatically copied into scoped memory. Back up `data/` before migrations. No rollback tool exists yet, so schema changes beyond version 1 must add explicit forward and rollback-safe migration tests before release.
