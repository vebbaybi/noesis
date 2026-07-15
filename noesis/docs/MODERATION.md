# Moderation

Inbound and outbound stages share a typed decision model. Stage one retains original text and analyzes
an NFKC/case-folded copy with zero-width removal, leetspeak translation, separator collapse and repeat
normalization. `glin-profanity` was not integrated because a supported Python distribution/API was not
verified. Stage two optionally uses Detoxify's `Detoxify(...).predict(...)` in a single bounded worker.

Defaults run stage one and report stage two as degraded. Production can enable Detoxify and choose
fail-closed behavior. Decisions expose direction, tenant, categories, thresholds, redacted evidence,
model version and failure state. Credible violence/threat is blocked; other configured matches warn.
