# JIT Context and Platform Tools

Evidence is untrusted data, never system instruction. Each evidence object contains source type/ID, retrieval time, scope, freshness, confidence, authorization, classification, tool ID, cache state, facts, and limitation.

The implemented Discord tool reads only metadata already present on the authorized current gateway event: guild name/member count when available, current channel name/type, and current thread archived/locked state. It performs no broad history fetch and no network request. Unauthorized calls fail closed with no facts.

Future tools must have a known ID, validated input, authorization and scope, timeout, size limit, provenance, audit record, and no direct model-controlled execution. X, Slack, Teams, GitHub, Snapshot, Farcaster, and Web3 tools are not implemented.
