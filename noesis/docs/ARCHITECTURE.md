# Noesis architecture

Noesis uses one source package, ten ownership roots, and one composition root. The executable shim
`noesis_agent.runner` delegates immediately to `noesis_agent.runtime.bootstrap`.

## Layers and ownership

- `domain`: deterministic platform-neutral entities and contracts. It never imports an adapter.
- `application`: use cases and narrow ports. It does not construct SDK, configuration, or storage adapters.
- `cognition`: NLU, reasoning, response planning, prompts, provider routing, and local fallback.
- `memory`: memory semantics, retrieval, retention, redaction, and autonomous-memory policy.
- `capabilities`: bounded content, media, moderation, publishing, and scheduling features.
- `interfaces`: inbound FastAPI and command translation.
- `integrations`: Discord, X, LLM, audio, HTTP, and other external adapters.
- `infrastructure`: configuration, persistence, observability, concurrency, and technical support.
- `runtime`: dependency construction, lifecycle, background supervision, and process startup.
- `shared`: narrow logging/error/identifier primitives with no feature ownership.

Dependency direction is inward: domain is independent; application describes needs; cognition,
memory, and capabilities provide owned behavior; interfaces and adapters translate boundaries; runtime
is the only layer that assembles concrete objects. Nothing outside `runtime` imports runtime.

## Canonical event and runtime flow

`runner -> runtime.bootstrap -> runtime.lifecycle -> runtime.container -> interface/integration ->
application mention or conversation use case -> cognition router/local fallback -> memory -> output adapter`.

FastAPI is constructed in `interfaces/api/app.py`. Discord events are translated in
`integrations/mention_normalizers.py` before application handling. Provider-specific payloads do not
enter domain contracts.

## Cognition and memory

`cognition/providers.py` is the application-facing provider router; its local provider is the
credential-free fallback. `cognition/engine.py` owns context construction and response planning.

`memory/service.py` is the memory facade. Working, episodic, semantic, scoped, and autonomous memory
remain behaviorally distinct. SQLite and JSON storage construction is owned by runtime/infrastructure;
redaction and retention decisions remain in memory.

## Optional dependencies

Audio integrations import native/ML libraries lazily. Base installation does not require the `audio`
extra. External providers are credential-gated, and tests never perform live sends.

## Placement rule

Put request DTOs next to their interface, platform-neutral contracts in domain, orchestration in
application, provider code in integrations, database code in infrastructure, and construction only in
runtime. Do not add generic `models`, `services`, `clients`, `core`, or `utils` packages.
