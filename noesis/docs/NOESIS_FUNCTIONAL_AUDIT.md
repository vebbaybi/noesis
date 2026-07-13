# Noesis Functional Audit

Audit date: 2026-07-11. Scope: repository at branch `noesis-functional-hardening`.

## Structure and entry points

Noesis is a Python 3.10+ package in `src/noesis_agent`. `noesis_agent.runner:main` is the process entry point; `noesis_agent.api.app:app` is the FastAPI entry point. Configuration lives in `config`, domain models in `models`, orchestration in `services`/`core`, persistence in `store`, and platform code in `clients`, `platforms`, and `monitors`. Tests are in `tests`. A minimal credential-free GitHub Actions workflow compiles the source and runs the test suite.

The API includes health/state, planning, session lifecycle, transcript, host-turn, summary/artifact, X publish, realtime configuration, and local mention dry-run routes. Runtime profiles are development, test, staging, and production; unknown profile names deliberately fall back to development, while an invalid `NOESIS_ENV` fails validation clearly.

## Capability matrix

| Capability | State | Evidence / limit |
|---|---|---|
| Import and local API | Implemented and tested | FastAPI app and `/health`; no credentials required. |
| Session/transcript/host workflows | Implemented locally | Existing services and API workflow tests. Persistent JSON data is local. |
| Mention normalization/decision/intent/reply | Implemented and tested locally | `MentionEvent`, `MentionService`, and both dry-run endpoints. |
| Operator UI | Implemented and tested locally | `/operator` provides safe status and dry-run testing; it is loopback-only and has no authentication claim or live controls. |
| Deterministic local NLP | Implemented and offline-tested | Heuristic structured interpretation reports confidence and limitations; no trained-model accuracy claim. |
| Scoped durable memory | Implemented and offline-tested | SQLite schema v1 supports restart persistence, strict scope filters, lexical retrieval, expiry, correction, and deletion. Automatic JSON migration and embeddings are not implemented. |
| Discord JIT metadata | Implemented and offline-tested | Authorized current-event guild/channel/thread metadata only; no broad history or additional network fetch. |
| Local response fallback | Implemented and tested | Deterministic, limitation-aware responses; no network calls. |
| OpenAI text generation | Implemented, credential-gated, not live-verified | Async client is created only with `OPENAI_API_KEY`; failures fall back in mention handling. |
| Discord bot/chat | Runtime-wired and mock-tested, credential-gated, not live-verified | The production background manager binds the bot callback through normalization, `MentionService`, dispatcher, and the original message reply target. Two explicit live-send flags default false. No credential was supplied. |
| X reads/writes | Implemented, credential-gated, not live-verified | Tweepy monitor has a normalized callback path; dictionary event normalization and dry-run dispatch are tested. Live permissions/account access were not supplied. |
| X Spaces hosting | Partial/not verified | Models/adapters exist, but X API does not provide the complete live audio hosting path used by the product concept. |
| Audio transcription | Partial, optional | Faster Whisper can be loaded lazily with audio extras. Hardware/models were not verified. |
| Diarization | Partial, optional | pyannote-backed code exists; model access and runtime dependencies were not verified. |
| Realtime audio | Partial | Endpoint prepares configuration; it does not mint a live token or prove a live session. |
| Publishing/media helpers | Local generation implemented | Live destinations remain credential/platform dependent. |

## Findings

Working code is concentrated around the API, local JSON-backed sessions, transcript handling, deterministic content helpers, provider routing, and adapter dry runs. Missing Discord, X, and OpenAI credentials do not prevent imports or local startup. Heavy audio packages are optional extras.

The README was replaced with a concise verified-status document. It labels Discord, X, OpenAI, audio, realtime, and X Spaces behavior by actual verification level and links to this audit and the runbook.

The normalized mention path was missing. It now detects explicit mentions/replies, classifies questions, explanation, summarization, project help, bugs, feature requests, contribution requests, casual mentions, and hostile/unclear input. It rejects duplicate/unaddressed events, limits payload sizes, uses supplied parent context only, reports missing provider capability, and never claims a live send. Duplicate protection is process-local and resets on restart.

Discord channel authorization now distinguishes real `discord.Thread` instances from ordinary channels. Directly allowlisted channels pass; a confirmed thread may inherit only from its resolved allowlisted parent ID. The actual thread remains the conversation and response target. Rejections occur before normalized mention processing. Deduplication is bounded and keyed by platform plus event ID.

Potential dead/stale surface remains broad: numerous small audio, platform, knowledge, scheduling, telemetry, and media modules have limited direct integration with the runtime. They should not be deleted without usage analysis. The untracked working-tree deletion `noesis/rump` predates this pass and was preserved.

## Verification and limits

Latest verification on 2026-07-13: `python -m compileall -q src` passed and `python -m pytest -q` passed all 81 tests in 52.69 seconds. FastAPI import, `/health`, and `/operator` smoke checks passed. No live calls were made and no secrets were available, so Discord delivery, X delivery/reads, OpenAI output quality, audio devices/models, and external rate limits cannot be claimed as verified.

## Fix now versus roadmap

Fixed now: shared mention models/service, honest deterministic fallback, duplicate/empty/unaddressed handling, provider-failure fallback, dry-run API endpoints, and behavior tests.

Next implementation work: complete the controlled private-channel Discord/thread checklist; add safe audit persistence before building the operator event viewer; improve bounded context acquisition within platform permission limits; and add new platform adapters only through the normalized event/dispatch contracts.

Roadmap work: production credential validation/deployment, live adapter integration tests in controlled accounts, durable queue/rate limits, observability, and optional audio validation on supported hosts.
