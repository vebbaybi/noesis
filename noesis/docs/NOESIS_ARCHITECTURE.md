# Noesis Architecture

## Implemented and offline-tested

`python -m noesis_agent.runner` owns lifecycle validation, the FastAPI/operator server, and enabled platform background services. Platform adapters authorize first, normalize into `MentionEvent`, and preserve an exact response target. Shared cognition performs bounded deduplication, deterministic local interpretation, optional evidence use, provider routing, fallback, and dispatch.

The durable memory boundary is local SQLite with transactions, foreign keys, schema-version records, WAL, indexed scope columns, expiry, deletion, correction/supersession, and lexical retrieval. Existing JSON/session memory remains accessible; automatic JSON migration is not implemented.

Discord has one authorized metadata tool for facts already present on the current gateway event. Tool results are typed evidence and cannot dispatch actions. X normalization exists; X live cognition tools remain unimplemented.

## Runtime boundaries

- Critical: settings validation and API startup when enabled.
- Optional/degraded: Discord, X, OpenAI, ELKA, local models, audio, and external sources.
- Platform authorization precedes cognition, memory, tools, and dispatch.
- Missing optional components preserve deterministic local operation.

## Planned

Typed event-bus persistence, supervised component state transitions, async memory workers, bounded conversation windows, additional platform tools, connectors, local inference, feedback datasets, and remote operator security are planned—not current capabilities.
