# Noesis Functional Audit

Audit date: 2026-07-11. Scope: repository at branch `noesis-functional-hardening`.

## Structure and entry points

Noesis is a Python 3.10+ package in `src/noesis_agent`. `noesis_agent.runner:main` is the process entry point; `noesis_agent.api.app:app` is the FastAPI entry point. Configuration lives in `config`, domain models in `models`, orchestration in `services`/`core`, persistence in `store`, and platform code in `clients`, `platforms`, and `monitors`. Tests are in `tests`. No CI workflow is present in this checkout despite the README referring to one.

The API includes health/state, planning, session lifecycle, transcript, host-turn, summary/artifact, X publish, realtime configuration, and local mention dry-run routes. Runtime profiles are development, test, staging, and production; unknown profile names deliberately fall back to development, while an invalid `NOESIS_ENV` fails validation clearly.

## Capability matrix

| Capability | State | Evidence / limit |
|---|---|---|
| Import and local API | Implemented and tested | FastAPI app and `/health`; no credentials required. |
| Session/transcript/host workflows | Implemented locally | Existing services and API workflow tests. Persistent JSON data is local. |
| Mention normalization/decision/intent/reply | Implemented and tested locally | `MentionEvent`, `MentionService`, and both dry-run endpoints. |
| Local response fallback | Implemented and tested | Deterministic, limitation-aware responses; no network calls. |
| OpenAI text generation | Implemented, credential-gated, not live-verified | Async client is created only with `OPENAI_API_KEY`; failures fall back in mention handling. |
| Discord bot/chat | Implemented, credential-gated, not live-verified | py-cord client, commands, and output adapter exist. No credential was supplied. Mention events are not yet wired from the live bot into the new normalized path. |
| X reads/writes | Implemented, credential-gated, not live-verified | Tweepy client, mention polling, and dry-run posting exist. Live permissions/account access were not supplied. Monitor is not yet wired into the normalized mention service. |
| X Spaces hosting | Partial/not verified | Models/adapters exist, but X API does not provide the complete live audio hosting path used by the product concept. |
| Audio transcription | Partial, optional | Faster Whisper can be loaded lazily with audio extras. Hardware/models were not verified. |
| Diarization | Partial, optional | pyannote-backed code exists; model access and runtime dependencies were not verified. |
| Realtime audio | Partial | Endpoint prepares configuration; it does not mint a live token or prove a live session. |
| Publishing/media helpers | Local generation implemented | Live destinations remain credential/platform dependent. |

## Findings

Working code is concentrated around the API, local JSON-backed sessions, transcript handling, deterministic content helpers, provider routing, and adapter dry runs. Missing Discord, X, and OpenAI credentials do not prevent imports or local startup. Heavy audio packages are optional extras.

The previous README overstates current live operation (for example, X feed mastery and realtime tokens). It also contains a pasted design/build essay and stale dependency claims. The runbook and this audit are authoritative for verified state.

The normalized mention path was missing. It now detects explicit mentions/replies, classifies questions, explanation, summarization, project help, bugs, feature requests, contribution requests, casual mentions, and hostile/unclear input. It rejects duplicate/unaddressed events, limits payload sizes, uses supplied parent context only, reports missing provider capability, and never claims a live send. Duplicate protection is process-local and resets on restart.

Potential dead/stale surface remains broad: numerous small audio, platform, knowledge, scheduling, telemetry, and media modules have limited direct integration with the runtime. They should not be deleted without usage analysis. The untracked working-tree deletion `noesis/rump` predates this pass and was preserved.

## Verification and limits

Verification on 2026-07-11: `python -m compileall -q src` passed and `python -m pytest -q` passed all 50 tests in 19.50 seconds. The FastAPI health smoke test passed when run with the source package on `PYTHONPATH`. No live calls were made and no secrets were available, so Discord delivery, X delivery/reads, OpenAI output quality, audio devices/models, and external rate limits cannot be claimed as verified.

## Fix now versus roadmap

Fixed now: shared mention models/service, honest deterministic fallback, duplicate/empty/unaddressed handling, provider-failure fallback, dry-run API endpoints, and behavior tests.

Next implementation work: wire Discord and X raw event shapes into `MentionEvent`; add platform-specific senders behind explicit live/dry-run selection; persist deduplication where multiple workers are used; improve context acquisition within platform permission limits; and replace the realtime configuration endpoint with a documented real flow or rename it.

Roadmap work: production credential validation/deployment, live adapter integration tests in controlled accounts, durable queue/rate limits, observability, and optional audio validation on supported hosts.
