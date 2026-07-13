# Autonomous actionable memory

## Implemented and offline-tested

The live platform-neutral mention path can extract decisions, tasks, blockers, corrections,
dated project facts, unresolved questions, and stable preferences without an explicit
“remember” command. Discord authorization happens before normalization and cognition.
Ambient processing remains `mentions_only` by default and can be enabled explicitly with
`NOESIS_MEMORY_OBSERVATION_MODE`.

All candidates pass through application-controlled thresholds and secret rejection. Scope is
derived from normalized platform metadata; message text cannot broaden it. Stable identities
combine platform, event, candidate type, canonical content, and scope. Replays therefore do not
create duplicate active records.

SQLite runs in WAL mode through a dedicated bounded executor. It has a fixed worker count,
bounded pending capacity, timeouts, backpressure, safe error reporting, and graceful shutdown.
Each operation opens its own connection; connections are not shared across workers.

## Scoring and retention

Candidates carry confidence, importance, actionability, source-event provenance, retention
class, and task state where applicable. Current persistent thresholds default to `0.7`.
Greetings, random low-value chat, and secret-bearing content are rejected. Live counts and
presence are evidence, not durable semantic memory.

Corrections and completion statements supersede the most recent compatible active record in the
same exact platform/guild/channel/conversation scope. Superseded, expired, and deleted records
are excluded from active retrieval. Task assignments extract a deterministic assignee and common
natural-language deadline when present.

## Scope isolation and poisoning controls

Retrieval is bounded and checks platform, guild, channel, conversation, and optional user scope.
Raw platform text is untrusted. It cannot request global scope, bypass the write gate, enable
training, or change policy. Operator previews omit candidate content and redact sensitive stored
previews. Dry-run cognition extracts candidates but performs no memory write or production-memory
retrieval.

## Moderation boundary

Credential exposure, threats, scam indicators, targeted insults, and untargeted profanity are
classified separately. Harmful content is not written as ordinary semantic memory. The current
default is advisory and silent: moderation signals are counted and safely summarized, while
punitive actions remain unimplemented and require future human-approved policy.

## External-validation limitations

The Discord gateway integration is mock-tested and runner-tested locally. Ambient behavior has
not been exercised against a live Discord guild in this implementation pass. X and X Spaces
capabilities remain credential- or platform-blocked and are classified as such in the capability
registry.
