# Architecture migration

Baseline: commit `c5f038417b4dcbe2b7e96ed910f03f8d376b2f2b`, branch
`noesis-local-first-cognition`, with a large user-owned migration already uncommitted. That work was
preserved and continued on `noesis-architecture-consolidation`. The preserved baseline compiled and
had 153 passing tests.

## Tree migration

| Previous module root | Canonical destination | Action |
| --- | --- | --- |
| `api`, `commands` | `interfaces/api`, `interfaces/commands` | moved |
| `audio` | `integrations/audio` | moved; optional imports retained |
| `clients` | `integrations/discord`, `integrations/x`, `integrations/llm` | split by provider |
| `config` | `infrastructure/config` | moved; project-root discovery corrected |
| `content`, `media`, `moderation`, `publishing`, `scheduling` | `capabilities/*` | bounded by feature |
| `knowledge`, `prompts`, `brain` | `cognition/knowledge`, `cognition/prompts`, `cognition/*` | consolidated |
| `models` | `domain/entities`, `domain/contracts` | warehouse dismantled by ownership |
| `persistence`, `store` | `infrastructure/persistence` | consolidated |
| `monitors`, `telemetry` | `runtime/monitors`, `infrastructure/observability` | split by lifecycle vs telemetry |
| `pipelines`, `services` | `application/*`, `runtime/*`, capability facades | split by responsibility |
| `utils` | `shared` and `infrastructure/support` | split; legacy root deleted |
| `runner.py` | `runtime/bootstrap.py` | retained only as executable shim |

Deleted roots: `brain`, `core`, `services`, `pipelines`, `monitors`, `store`, `models`, `clients`,
`platforms`, `api`, `audio`, `commands`, `config`, `content`, `knowledge`, `media`, `moderation`,
`persistence`, `prompts`, `publishing`, `scheduling`, `telemetry`, and `utils`.

The only compatibility shim is `noesis_agent.runner`; removal can occur after downstream process
managers adopt the `noesis` console script or `noesis_agent.runtime.bootstrap`.

Behavior preserved: FastAPI/operator routes, Discord-shaped event handling, provider routing and local
fallback, SQLite/autonomous memory, profile fallback, lazy optional audio, background lifecycle, and
credential-free tests. No live Discord/X messages or external provider calls were made.

Follow-up work belongs to NLP/ML modernization: implement the existing provider contracts with a
tokenizer, embeddings, classifier, reranker, vector store, and evaluation harness without changing
runtime or interface ownership.
