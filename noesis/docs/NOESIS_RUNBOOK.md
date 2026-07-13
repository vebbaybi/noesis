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

Run the complete local runtime with `python -m noesis_agent.runner`. This single process starts the configured API/operator server plus enabled background services such as Discord. Open `http://127.0.0.1:8000/`; it redirects to `/operator`. It is local-only, shows configuration presence/readiness rather than values, and offers dry-run mention testing. It has no live-send controls and no remote authentication; do not expose it publicly.

Operator storage status uses only a label and configured/available/writable booleans; it does not return the host data path. Scoped SQLite memory initializes under the configured data directory and supports lexical retrieval without embeddings or external providers.

Running `python -m uvicorn noesis_agent.api.app:app --reload` is a UI/API development mode only; it does not start Discord or other runner-managed background services. `0.0.0.0` is a server bind address, not a browser URL—use `127.0.0.1` or `localhost` in the browser.

Dry-run mention test:

```bash
curl -X POST http://127.0.0.1:8000/respond/dry-run -H "Content-Type: application/json" -d "{\"event_id\":\"demo-1\",\"platform\":\"local\",\"text\":\"@Noesis summarize this\",\"parent_text\":\"The supplied text to summarize.\"}"
```

`POST /events/mention/test` is an equivalent explicit test route. `POST /events/mention/raw/test` accepts a `platform` of `discord` or `x` plus a raw-shaped `event` dictionary and exercises normalization and outbound dry-run dispatch. Responses identify intent, send mode, reason, and missing capability. These endpoints never send to a platform.

## Environment

Core variables: `NOESIS_ENV` selects development/test/staging/production; `NOESIS_PROFILE` optionally overrides the runtime profile; `NOESIS_HOST`, `NOESIS_PORT`, and `NOESIS_ENABLE_API` control serving; `NOESIS_DATA_DIR` and `NOESIS_LOG_DIR` select local paths; `NOESIS_NAME` controls mention detection.

Provider variables: `OPENAI_API_KEY` enables OpenAI text calls; `NOESIS_DEFAULT_MODEL` and `NOESIS_REALTIME_MODEL` select models; `NOESIS_COGNITION_PROVIDER` selects auto/local/elka; ELKA additionally needs `NOESIS_ENABLE_ELKA=true`, `ELKA_BASE_URL`, and optionally `ELKA_API_KEY`.

Discord: enable with `NOESIS_ENABLE_DISCORD=true` and set `DISCORD_BOT_TOKEN`. Guild/voice/channel IDs constrain live behavior. `NOESIS_ENABLE_LIVE_AGENT`, auto-start variables, and cross-post flags should remain false until the bot permissions and channel IDs are verified.

Discord mention replies require both `NOESIS_ENABLE_LIVE_MENTION_SEND=true` and `NOESIS_ENABLE_DISCORD_MENTION_SEND=true`. Both default to false. With either switch off, mentions may be normalized and processed, but the dispatcher reports a disabled state and does not call Discord. OpenAI remains optional; without it, the deterministic local responder is used.

An allowlisted Discord text channel also authorizes structurally confirmed Discord threads whose parent is that channel. Operators must not add individual thread IDs. Authorization uses the parent channel, but replies and normalized response-target metadata keep the originating thread ID.

## Controlled Discord live test checklist

Use a private test server and channel; do not begin with a public deployment.

1. Create a private Discord test server/channel.
2. Add the bot with permission to view the channel, read message history, and send/reply to messages. Enable the required message-content intent in the Discord developer portal.
3. Set `NOESIS_ENABLE_DISCORD=true` and provide `DISCORD_BOT_TOKEN` in the uncommitted `.env` file.
4. Restrict `DISCORD_ALLOWED_TEXT_CHANNEL_IDS` to the private test channel.
5. Set `NOESIS_ENABLE_LIVE_MENTION_SEND=true` and `NOESIS_ENABLE_DISCORD_MENTION_SEND=true` explicitly.
6. Run `python -m noesis_agent.runner`.
7. Mention Noesis once and confirm exactly one reply.
8. Confirm sanitized logs contain the source event ID, `succeeded`, and the Discord delivery receipt ID—never the token.
9. Replay or inject the same message ID in a controlled test and confirm no second sender call. Ordinary Discord messages have unique IDs, so this check may require a fixture or gateway replay harness.
10. Turn both live-send switches off after the test.

Live Discord behavior remains unverified until this checklist succeeds. X live delivery is a later milestone.

X: enable with `NOESIS_ENABLE_X=true`; writes require `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, and `X_ACCESS_TOKEN_SECRET`. `X_BEARER_TOKEN` supports applicable reads. `X_HANDLE` identifies the account. Keep cross-post disabled until a dry run is reviewed.

Never commit `.env`. Live Discord/X/OpenAI behavior is credential- and permission-dependent and is not exercised by the local test suite.
