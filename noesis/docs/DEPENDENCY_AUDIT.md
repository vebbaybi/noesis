# Dependency audit

| Package | Constraint | Role / API verified | Group | License / status |
| --- | --- | --- | --- | --- |
| LiteLLM | `>=1.74.15,<1.75` | async `acompletion`, normalized OpenAI-compatible providers | local-llm | MIT; verified install on Windows/Python 3.12; newer 1.92 source build blocked by missing Rust |
| qdrant-client | `>=1.14,<2` | `AsyncQdrantClient`, collection/index/upsert/query lifecycle | rag | Apache-2.0; optional |
| fastembed | `>=0.7,<1` | `TextEmbedding`, supported-model metadata, query/passage embedding | rag | Apache-2.0; optional |
| redis | `>=5.2,<9` | `redis.asyncio.from_url`, pooled async SET NX/EX and close | coordination | MIT; optional |
| Detoxify | `>=0.5.2,<1` | 0.5.2 locally verified: `Detoxify(model, device).predict(text)`; blocking worker | moderation | Apache-2.0; CPU model validated with Torch 2.13.0 |
| faster-whisper | `>=1.0.3` | existing lazy STT adapter | audio | MIT; optional/heavy |
| py-cord | `>=2.7,<3` | existing Discord gateway/application integration | discord/base compatibility | MIT |
| httpx2 | `>=2.5,<3` | Starlette TestClient transport | dev | BSD-3-Clause; replaces deprecated plain-httpx test transport |

`glin-profanity` is blocked: the requested Python distribution, import path, maintenance and Python
3.11 support could not be established reliably. No substitute package is silently represented as it.
Dependency constraints intentionally leave patch selection to the installer; reproducible production
images should consume an organization-maintained constraints file after vulnerability review.
