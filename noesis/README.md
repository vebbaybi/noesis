# Noesis Agent

Noesis is an experimental Python agent/control plane for local session workflows, host responses, and community mention handling. It is not production-ready.

## Verified locally

- The FastAPI application imports and `GET /health` works without credentials.
- Session, transcript, planning, host-response, and local persistence workflows have automated tests.
- Platform-neutral mention handling supports deterministic local fallback, intent detection, duplicate suppression, and honest limitation messages.
- `POST /respond/dry-run`, `POST /events/mention/test`, and `POST /events/mention/raw/test` test local, Discord-shaped, and X-shaped mentions without sending externally.
- The local-only `/operator` page shows safe readiness state and runs platform-neutral mention dry runs without exposing credentials or enabling live sends.

Discord, X, and OpenAI behavior is credential-gated. The Discord runtime mention pipeline is wired and mock-tested, but live replies are disabled by default and have not been verified against Discord. X live delivery and live OpenAI output are also unverified. Audio, transcription, diarization, realtime audio, and X Spaces support are partial or optional and must not be treated as proven live capabilities.

## Local setup

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
# Copy .env.example to .env using the command appropriate for your shell.
python -m uvicorn noesis_agent.api.app:app --reload
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
