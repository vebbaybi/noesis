# CI container failure analysis

## Confirmed cause

The `compose-cpu` failure was an application startup failure, not a slow health-check loop. The
Noesis process ran as its intended non-root user and exited while configuring logging:

```text
PermissionError: [Errno 13] Permission denied: '/opt/venv/lib/python3.12/logs'
```

The traceback passed through `NoesisLogger`, `configure_logging`, and `_build_handlers` before the
API server started. Consequently nothing bound to `0.0.0.0:8000`, so `/live` and `/ready` could not
be reached.

## Contributing causes

- The runtime log location was not explicit, allowing it to resolve beneath the read-only virtual
  environment rather than the mutable application-data directory.
- A named volume replaces the image's `/app/.noesis_data` directory. Image ownership alone cannot
  prove that the mounted path remains writable, so the smoke test lacked a volume-write assertion.
- The Dockerfile probed `/health`, while the hardened runtime contract and CI use `/live` and
  `/ready`.
- An earlier run also failed because `operator.html` was absent from the built wheel. Packaging was
  repaired separately and the wheel resource test now guards it.
- The base Compose configuration referred to an optional Ollama endpoint even when that profile
  was not intended to run, making basic startup less deterministic.

## Rejected hypotheses

- **Defective wait loop:** logs show the process repeatedly exited before a connection was possible.
- **API binding only to localhost:** the failure occurred before Uvicorn started; the repaired
  configuration explicitly uses `0.0.0.0:8000`.
- **Redis or Qdrant health:** both dependency services reached their Compose health gates; the
  Noesis traceback was a local filesystem error.
- **Ollama credentials or reachability:** the failing process did not reach model-provider startup.
  The CI override nevertheless disables local and external LLMs.
- **FastEmbed warming:** the traceback occurred during logging initialization. CI now disables RAG
  in the container smoke and tests real FastEmbed behavior in the integration job instead.
- **Missing package data in the latest run:** `operator.html` was present after the preceding
  packaging repair; the later artifact exposed the independent permission failure above.

## Evidence

The failed Actions artifact contains the repeated traceback and immediate restarts. Static image
inspection also showed that the runtime is deliberately non-root and that the historical default
could resolve a relative log directory beneath `/opt/venv/lib/python3.12`. Docker was not available
on the local validation host, so `compose ps`, `logs`, `inspect`, filesystem ownership, effective
environment, and socket binding could not be reproduced locally. The corrected workflow prints
those facts inline on every failure instead of hiding them only in an artifact.

## Repair

- The image creates `/app/.noesis_data/{logs,tmp,cache}` with UID/GID `10001:10001` before changing
  users and explicitly sets both data and log directories.
- The Dockerfile and Compose health checks consistently probe `/live`; the smoke additionally
  verifies `/ready` for the selected CI profile.
- `compose.ci.yml` disables both LLM paths, model credentials, RAG/FastEmbed startup, and outbound
  platform integrations while retaining Redis and Qdrant connectivity checks.
- Ollama and the local-model Noesis service are isolated behind the `local-model` profile.
- The installed wheel is the runtime source; the final image does not add a second writable source
  tree.

## Regression tests

The container-smoke job now proves that:

1. Compose configuration and image build succeed.
2. The image user is non-root.
3. Noesis, Redis, and Qdrant become healthy with bounded waits.
4. `/live` and `/ready` respond.
5. The non-root process can create, read, and delete a file through the named data volume.
6. Redis and Qdrant accept real round trips from the Compose network.
7. Noesis remains healthy after a restart and shuts down cleanly.
8. Process state, health, and sanitized logs are printed before any failure artifact is uploaded.
