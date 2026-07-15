# Deployment

Install base with `pip install -e .`, development with `pip install -e ".[dev]"`, and intelligence
services with `pip install -e ".[rag,local-llm,coordination]"`. Heavy moderation/audio dependencies are
separate extras. `compose.yml` binds only the API to loopback; Qdrant, Redis and Ollama remain internal.
Qdrant is durable, Redis is deliberately ephemeral, and model/data caches use named volumes.

Copy `.env.example` to `.env`, explicitly enable each optional capability, and never commit that file.
The health response distinguishes per-capability disabled, unavailable, ready and degraded states.
The image uses a multi-stage build and a non-root user. GPU deployment remains hardware blocked until
the target Docker host and accelerator configuration are validated.
