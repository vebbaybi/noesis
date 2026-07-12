# Noesis Roadmap Seed

## Now

- Verify the runtime-wired Discord mention pipeline in a private channel. Evidence: the production background manager now binds normalization, response, dispatch, and original-message reply; mocks prove one-send and duplicate behavior. Required: explicit live flags, private bot credentials, permissions, and manual receipt checks. Acceptance: one mention yields exactly one reply and sanitized logs record source/delivery IDs.
- Keep X live delivery deferred until Discord verification passes. Evidence: X normalization/dry-run exists, but this milestone intentionally does not wire live sending. Required later: controlled X account, permissions, rate-limit review, and receipt validation.

## Next

- Durable deduplication and rate limiting. Evidence: current dedupe is process-local and monitors poll. Required: bounded persistent/shared store with expiry. Acceptance: duplicates are suppressed across restart/workers and users receive no spam burst.
- Context retrieval within permissions. Evidence: models accept parent context but platform wiring does not fetch thread history. Required: adapter-specific bounded context fetch. Acceptance: responses cite only payload/fetched context and disclose unavailable history.
- Controlled live integration tests. Evidence: Discord/X/OpenAI code is unverified without credentials. Required: sandbox accounts, secret-managed CI job, and opt-in tests. Acceptance: delivery receipts and provider identities are asserted without exposing secrets.

## Later

- Production observability and queues. Evidence: telemetry helpers exist but the mention path is synchronous/in-memory. Required: metrics, structured safe audit events, retry policy, and worker design. Acceptance: latency/error/dedupe metrics and bounded retries are demonstrated.
- Validate optional audio/transcription/diarization on named host profiles. Evidence: implementations and extras exist, but models/hardware were not tested. Required: supported-device matrix and fixture-based tests. Acceptance: documented install and reproducible sample transcription on each supported profile.

## Deferred

- Autonomous X Spaces hosting and large-scale multi-platform expansion. Evidence: platform skeletons exist, but the core live transport and production mention delivery are not proven. Required: platform capability/legal/API review after foundations pass. Acceptance criteria should be written only once a supported integration path is confirmed.
- New memory/vector infrastructure. Evidence: local memory already exists; no measured retrieval bottleneck justifies a new dependency. Required: usage and quality data first. Acceptance: defer until a concrete reliability or scale requirement is demonstrated.
