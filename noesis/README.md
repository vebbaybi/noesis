# Noesis Agent

Noesis now has a canonical local-first intelligence path for live text events. It applies inbound and
outbound moderation, tenant-isolated semantic retrieval, structured LLM outcomes, allowlisted tools,
idempotency, and explicit degraded health states. The base install stays lightweight; use
`.[rag,local-llm,coordination]`, `.[moderation]`, or `.[audio]` only for enabled capabilities.

See [AI stack](docs/AI_STACK.md), [RAG and memory](docs/RAG_AND_MEMORY.md),
[moderation](docs/MODERATION.md), and [deployment](docs/DEPLOYMENT.md).

Noesis is an experimental Python agent/control plane for local session workflows, host responses, and community mention handling. It is not production-ready.

## Verified locally

- The FastAPI application imports and `GET /health` works without credentials.
- Session, transcript, planning, host-response, and local persistence workflows have automated tests.
- Platform-neutral mention handling supports deterministic local fallback, intent detection, duplicate suppression, and honest limitation messages.
- `POST /respond/dry-run`, `POST /events/mention/test`, and `POST /events/mention/raw/test` test local, Discord-shaped, and X-shaped mentions without sending externally.
- The local-only `/operator` page shows safe readiness state and runs platform-neutral mention dry runs without exposing credentials or enabling live sends.
- Authorized ambient Discord events can produce scoped actionable-memory candidates when the operator explicitly enables an observation mode.
- Autonomous memory uses a bounded dedicated executor, secret rejection, idempotent event identities, scoped retrieval, and correction/task supersession.
- `/operator/capabilities` classifies the complete `assets/users_request.md` catalogue without presenting planned behavior as implemented.

Discord, X, and OpenAI behavior is credential-gated. The Discord runtime mention pipeline is wired and mock-tested, but live replies are disabled by default and have not been verified against Discord. X live delivery and live OpenAI output are also unverified. Audio, transcription, diarization, realtime audio, and X Spaces support are partial or optional and must not be treated as proven live capabilities.

## Local setup

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
# Copy .env.example to .env using the command appropriate for your shell.
noesis
# Compatibility command: python -m noesis_agent.runner
```

No credentials are required for compilation, tests, health checks, or mention dry runs. External integrations are disabled by default in `.env.example`; never commit `.env`. Install `.[audio]` only on hosts that need the optional native/ML audio stack.

## Verification

```bash
python -m compileall -q src
python -m pytest -q
```

See the repository-grounded documentation:

- [Functional audit](docs/NOESIS_FUNCTIONAL_AUDIT.md)
- [Runbook](docs/NOESIS_RUNBOOK.md)
- [Roadmap seed](docs/NOESIS_ROADMAP_SEED.md)
- [Operator GUI plan](docs/NOESIS_OPERATOR_GUI_PLAN.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Architecture migration](docs/ARCHITECTURE_MIGRATION.md)
- [Dependency rules](docs/DEPENDENCY_RULES.md)
- [Local cognition](docs/NOESIS_LOCAL_COGNITION.md)
- [Memory policy](docs/NOESIS_MEMORY_POLICY.md)
- [JIT tools](docs/NOESIS_JIT_TOOLS.md)
- [Security threat model](docs/NOESIS_SECURITY_THREAT_MODEL.md)
- [Autonomous actionable memory](docs/NOESIS_AUTONOMOUS_MEMORY.md)
