# Containers

The base Compose stack is a credential-free local runtime: Noesis, Redis, and Qdrant. Ollama is an
explicit optional profile and is never part of the basic CPU smoke test.

## Concepts

- An **image** is the immutable packaged application.
- A **container** is a running image with an isolated filesystem and environment.
- A **named volume** persists mutable data independently of a container. Mounting it replaces the
  image directory at that path, which is why CI tests volume writability at runtime.
- `/live` proves the process and event loop are alive. `/ready` proves the selected runtime profile
  can serve requests. Docker health uses `/live`; callers should check both before sending work.

## Base stack

From the `noesis` directory:

```bash
docker compose config
docker compose build noesis
docker compose up -d --wait qdrant redis noesis
curl --fail http://127.0.0.1:8000/live
curl --fail http://127.0.0.1:8000/ready
docker compose ps --all
docker compose logs --no-color noesis
docker compose down --volumes
```

Noesis runs as non-root UID/GID `10001:10001`. Mutable data, logs, temporary files, and caches live
under `/app/.noesis_data`. The base stack disables local and external LLM calls but retains the
normal RAG configuration.

## Optional local model

Do not start the base `noesis` service at the same time because both services publish host port
8000. Start the profile's replacement service explicitly:

```bash
docker compose --profile local-model up -d --wait qdrant redis ollama noesis-local-model
docker compose --profile local-model logs -f noesis-local-model ollama
docker compose --profile local-model down
```

Pull or configure the required Ollama model according to the local-model guide before expecting
model-backed readiness. This profile does not enable external providers.

## CI smoke profile

The CI override is deterministic and does not download models:

```bash
docker compose -f compose.yml -f compose.ci.yml config
docker compose -f compose.yml -f compose.ci.yml up -d --build --wait qdrant redis noesis
docker compose -f compose.yml -f compose.ci.yml exec -T noesis sh -c \
  'p=/app/.noesis_data/.write-test; printf ok > "$p"; test "$(cat "$p")" = ok; rm "$p"'
docker compose -f compose.yml -f compose.ci.yml down --volumes
```

If startup fails, inspect `ps --all`, `logs noesis`, and `docker inspect noesis-noesis-1` before
teardown. Never put secrets in diagnostic output or committed Compose files.
