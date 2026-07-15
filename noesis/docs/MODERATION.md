# Moderation

Inbound and outbound stages share a typed decision model. Stage one retains original text and analyzes
an NFKC/case-folded copy with zero-width removal, leetspeak translation, separator collapse and repeat
normalization. `glin-profanity` was not integrated because a supported Python distribution/API was not
verified. Stage two optionally uses Detoxify's `Detoxify(...).predict(...)` in a single bounded worker.

Defaults run stage one and report stage two as degraded. Production can enable Detoxify and choose
fail-closed behavior. Decisions expose direction, tenant, categories, thresholds, redacted evidence,
model version and failure state. Credible violence/threat is blocked; other configured matches warn.

The stage-one implementation is project-owned `LexicalModerator`; `glin-profanity` is not used. It
supports policy allowlists and bounded evasion matching while preserving original text. Detoxify 0.5.2
with CPU Torch 2.13.0 was locally model-validated using the `original` checkpoint. Its observed labels
were `toxicity`, `severe_toxicity`, `obscene`, `threat`, `insult`, and `identity_attack`. Model loading
is lazy, inference uses one bounded executor, queue wait and inference have timeouts, and shutdown
cancels queued work and closes the executor. The downloaded checkpoint is held in the user Torch cache,
not the repository. GPU execution remains unvalidated.
