# Data Governance and Training Policy

Noesis does not train or fine-tune model weights from live messages. Raw platform events, private scopes, deleted content, logs, memories, reactions, and tool results are not training data by default.

No training pipeline is implemented. Future candidate collection requires consent and scope verification, redaction, deduplication, poisoning review, human approval, immutable provenance/license manifests, fixed evaluation splits, safety and isolation evaluation, manual promotion, canary deployment, and rollback. Completion of an offline job must never promote a model automatically.
