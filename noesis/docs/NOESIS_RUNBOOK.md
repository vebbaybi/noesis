# Noesis Runbook

## Install and run locally

From the `noesis` directory:

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
copy .env.example .env
python -m uvicorn noesis_agent.api.app:app --host 127.0.0.1 --port 8000
```

On macOS/Linux use `cp` instead of `copy`. Local boot and tests require no credentials. Keep integrations disabled until their credentials are configured. Optional audio support is installed with `.[audio]`; it may also require OS audio drivers and model access.

## Test

```bash
python -m compileall -q src
python -m pytest -q
python -c "from noesis_agent.api.app import app; print(app.title)"
```

Health: `GET http://127.0.0.1:8000/health`.

Dry-run mention test:

```bash
curl -X POST http://127.0.0.1:8000/respond/dry-run -H "Content-Type: application/json" -d "{\"event_id\":\"demo-1\",\"platform\":\"local\",\"text\":\"@Noesis summarize this\",\"parent_text\":\"The supplied text to summarize.\"}"
```

`POST /events/mention/test` is an equivalent explicit test route. Responses identify intent, whether Noesis would respond, responder, reason, and missing capability. They do not send to a platform.

## Environment

Core variables: `NOESIS_ENV` selects development/test/staging/production; `NOESIS_PROFILE` optionally overrides the runtime profile; `NOESIS_HOST`, `NOESIS_PORT`, and `NOESIS_ENABLE_API` control serving; `NOESIS_DATA_DIR` and `NOESIS_LOG_DIR` select local paths; `NOESIS_NAME` controls mention detection.

Provider variables: `OPENAI_API_KEY` enables OpenAI text calls; `NOESIS_DEFAULT_MODEL` and `NOESIS_REALTIME_MODEL` select models; `NOESIS_COGNITION_PROVIDER` selects auto/local/elka; ELKA additionally needs `NOESIS_ENABLE_ELKA=true`, `ELKA_BASE_URL`, and optionally `ELKA_API_KEY`.

Discord: enable with `NOESIS_ENABLE_DISCORD=true` and set `DISCORD_BOT_TOKEN`. Guild/voice/channel IDs constrain live behavior. `NOESIS_ENABLE_LIVE_AGENT`, auto-start variables, and cross-post flags should remain false until the bot permissions and channel IDs are verified.

X: enable with `NOESIS_ENABLE_X=true`; writes require `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, and `X_ACCESS_TOKEN_SECRET`. `X_BEARER_TOKEN` supports applicable reads. `X_HANDLE` identifies the account. Keep cross-post disabled until a dry run is reviewed.

Never commit `.env`. Live Discord/X/OpenAI behavior is credential- and permission-dependent and is not exercised by the local test suite.
