# Noesis Roadmap Seed

## Now

- Bind normalized callbacks in the production runner. Evidence: Discord/X normalizers, callback surfaces, and dispatcher are tested, but controlled live account wiring is not verified. Required: explicit runner configuration and adapter receipt handling. Acceptance: sandbox-account checks prove one inbound mention produces at most one outbound reply.
- Verify outbound mention delivery. Evidence: dispatcher defaults to dry-run and reports disabled/missing credentials, but no live credentials were supplied. Required: controlled Discord/X accounts and manual permission checks. Acceptance: exact platform receipt IDs are recorded without secrets.

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
