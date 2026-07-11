# NOESIS Agent Rebuild

> Status: active foundation. The API, local session workflows, cognition fallback,
> and tests are implemented. External Discord, X, realtime audio, and publishing
> capabilities require credentials and may include platform-dependent adapters.

## Local setup

```bash
python -m venv .venv
# Activate .venv for your shell, then:
python -m pip install -e ".[dev]"
cp .env.example .env
python -m uvicorn noesis_agent.api.app:app --reload
```

No credentials are required for local compilation, tests, or `GET /health`.
Integrations are disabled by default in `.env.example`. Never commit `.env`.
Install `.[audio]` (or `.[full,dev]`) only on hosts that need local voice,
transcription, and diarization; those extras include large native/ML packages.

## Verification

```bash
python -m compileall -q src
python -m pytest -q
```

`.github/workflows/noesis-ci.yml` validates Python 3.10 and 3.12, smoke-tests
`/health`, and builds an installable artifact after successful non-PR runs.
Live deployment is intentionally disabled until a hosting target is selected.

**NOESIS** is an intelligent, autonomous AI co-host and solo-host agent built for **The 1807** — specializing in podcasts, X Spaces, and community-driven discussions with a strong focus on **NFT investments**, crypto trends, and Web3 culture.

NOESIS lives primarily on **X** (formerly Twitter) for real-time feed awareness, Spaces hosting, publishing threads/recaps, and audience engagement, while using **Discord** as a secondary control and community hub.

## Key Focus Areas
- **X-Centric Operation** — Deep integration with X feeds, trends, and Spaces for live, high-engagement content.
- **NFT & Investment Bias** — NOESIS is tuned to analyze NFT projects, market signals from X, floor prices, volume spikes, and investment narratives (with disclaimers: not financial advice).
- **Dual Hosting Modes** — Acts as an advanced **co-host** (real-time interjections, moderation, audience Q&A) or **solo host** (autonomous episode planning, monologue, simulated guests, full Spaces runs).
- **Multi-Platform Surfaces** — X for live audio + publishing; Discord for commands, community, and fallback control.

## Current Capabilities
- Plans episodes and X Spaces sessions (via `planner_service`)
- Generates host replies, moderation lines, social posts, and NFT-focused commentary
- Maintains long-running session state with local transcript storage
- Exposes a **FastAPI** control plane for starting sessions, fetching plans/replies, and managing state
- Runs a **Discord bot** for slash commands (/plan, /start-session, /nft-insight, etc.)
- Runs an **X publisher** service for threads, recaps, show notes, and NFT spotlights
- Prepares **OpenAI Realtime API** tokens for future voice integration
- Pulls real-time X feed context to stay "versed" in trends (especially NFTs via semantic/keyword monitoring)

## Planned / In-Progress Features
- **Advanced Co-Host Mode** — Real-time transcription ingestion → queued interjections, audience question handling from X replies/mentions, segue suggestions
- **Solo Host Autonomy** — Fully autonomous X Spaces runs: auto-plan topic (e.g., "Daily NFT Roundup"), generate monologue segments, role-play guest debates, end with CTA/thread publish
- **NFT Investment Depth** — Bias responses toward bullish/analytical takes on projects (e.g., Solana drops, blue-chips, emerging collections), pull X sentiment/volume signals, simulate portfolio tracking
- **Live X Feed Mastery** — Background service monitors NFT/crypto accounts, trends, and mentions to inform hosting in real time
- **Voice Layer** — Integrate OpenAI Realtime + TTS (e.g., ElevenLabs) for natural audio output; future direct X Spaces joining (note: X API currently supports lookup/search but not programmatic creation/hosting of Spaces — requires app/browser automation or manual start + bot audio injection)

Yeah. For NOESIS, the clean way is to build the scripts in **layers**, not as random files appearing from the void like cursed mushrooms after rain.

## How the scripts should be created

Build order should follow dependency gravity:

### 1. Foundation first

Create these first because everything else leans on them:

* `config/settings.py`
* `utils/`
* `models/`
* `store/`
* `core/event_bus.py`
* `services/container.py`

These define config, logging, validation, domain models, persistence, dependency wiring, and internal events. If this layer is sloppy, the whole agent becomes elegant nonsense.

### 2. Runtime shell

Then create the runtime skeleton:

* `core/bootstrap.py`
* `core/lifecycle.py`
* `core/orchestrator.py`
* `core/task_manager.py`
* `runner.py`
* `api/app.py`
* `api/routes/health.py`

This gives NOESIS startup, shutdown, task supervision, and API control.

### 3. Platform clients and adapters

Then build external connectivity:

* `clients/openai_client.py`
* `clients/discord_bot.py`
* `clients/x_client.py`
* `platforms/base.py`
* `platforms/discord_space.py`
* `platforms/x_space.py`

This separates raw API access from platform behavior. That separation matters because clients talk to services, but adapters define how NOESIS acts inside a room.

### 4. Audio stack

Then the hearing and speaking organs:

* `audio/input_stream.py`
* `audio/output_stream.py`
* `audio/vad.py`
* `audio/transcription.py`
* `audio/tts_pipeline.py`
* `audio/diarization.py`
* `audio/recording.py`

For a podcast and live spaces agent, this layer is not optional. OpenAI’s Realtime API is explicitly designed for low latency multimodal audio interactions, and the Python SDK notes realtime support over WebSockets. ([OpenAI Developers][1])

### 5. Conversation intelligence

Then give the beast a frontal cortex:

* `cognition/conversation_manager.py`
* `cognition/decision_engine.py`
* `cognition/response_planner.py`
* `cognition/persona_engine.py`
* `cognition/solo_host_mode.py`
* `cognition/cohost_manager.py`
* `cognition/guest_mode.py`
* `cognition/fact_guard.py`

This is where NOESIS stops being “bot that replies” and starts becoming “host that manages a room.”

### 6. Session and pipeline layer

Then the live flow:

* `services/session_service.py`
* `services/platform_service.py`
* `services/voice_service.py`
* `pipelines/pre_show.py`
* `pipelines/live_show.py`
* `pipelines/post_show.py`
* `pipelines/emergency_recovery.py`

This turns features into actual workflows.

### 7. Memory and research

Then give it history and prep:

* `memory/working_memory.py`
* `memory/episodic_memory.py`
* `memory/guest_memory.py`
* `memory/retrieval.py`
* `knowledge/researcher.py`
* `knowledge/briefing_builder.py`
* `knowledge/source_ranker.py`

Qdrant’s Python client is current and actively maintained, so it is a solid fit for vector retrieval in this layer. ([PyPI][2])

### 8. Moderation and publishing

Then the broadcast muscles:

* `moderation/room_moderator.py`
* `moderation/speaker_queue.py`
* `media/show_notes.py`
* `media/clip_extractor.py`
* `media/chapterizer.py`
* `services/publisher_service.py`
* `services/summary_service.py`

### 9. Telemetry and tests

Then observability and confidence:

* `telemetry/metrics.py`
* `telemetry/tracing.py`
* `telemetry/healthcheck.py`
* `tests/unit/`
* `tests/integration/`

FastAPI, Uvicorn, Pydantic 2.12, pydantic-settings 2.13.1, and OpenTelemetry FastAPI instrumentation are all current maintained pieces for this runtime shape. ([PyPI][3])

## Libraries involved by subsystem

### Core backend

* `fastapi`
* `uvicorn[standard]`
* `pydantic`
* `pydantic-settings`
* `httpx`
* `orjson`
* `python-dotenv`
* `tenacity`
* `structlog`

### OpenAI and reasoning

* `openai`
* `tiktoken`
* `websockets`

The current OpenAI Python library release is 2.28.0, and OpenAI’s docs show REST, streaming, and realtime APIs as first class paths. ([PyPI][4])

### Discord and X

* `discord.py`
* `tweepy`

`discord.py` remains the mainstream async Discord wrapper, and Tweepy remains an X API wrapper on PyPI. ([PyPI][5])

### Audio and realtime media

* `numpy`
* `sounddevice`
* `soundfile`
* `webrtcvad`
* `pydub`
* `librosa`
* `aiortc`
* `av`

`aiortc` is still the standard Python WebRTC library, useful if you later support browser rooms or custom live audio transport. ([PyPI][6])

### Memory and retrieval

* `qdrant-client`
* `redis`
* `sqlalchemy`
* `aiosqlite`

### Scheduling and jobs

* `apscheduler`
* `croniter`

### Telemetry

* `prometheus-client`
* `opentelemetry-api`
* `opentelemetry-sdk`
* `opentelemetry-instrumentation-fastapi`

### Media and post production

* `ffmpeg-python`
* `moviepy`
* `mutagen`

## Requirements strategy

For a project like NOESIS, do **not** hard pin every single package to exact patch versions on day one unless you are shipping reproducible deployments right now. That sounds disciplined, but it also becomes dependency tax season.

The sane move is:

* pin core framework families to compatible major and minor ranges
* keep media and platform extras slightly looser
* split optional heavy features later into `requirements-dev.txt`, `requirements-media.txt`, and `requirements-prod.txt`

But since you asked for a `requirements.txt`, here is a strong all in one starting point.

```txt
fastapi>=0.115,<1.0
uvicorn[standard]>=0.30,<1.0
pydantic>=2.12,<3.0
pydantic-settings>=2.13,<3.0

openai>=2.28,<3.0
tiktoken>=0.9,<1.0
websockets>=15,<16

httpx>=0.28,<1.0
orjson>=3.10,<4.0
python-dotenv>=1.0,<2.0
tenacity>=9.0,<10.0
structlog>=25.0,<26.0

discord.py>=2.5,<3.0
tweepy>=4.16,<5.0

numpy>=2.1,<3.0
sounddevice>=0.5,<1.0
soundfile>=0.13,<1.0
webrtcvad>=2.0.10,<3.0
pydub>=0.25,<1.0
librosa>=0.11,<1.0
aiortc>=1.9,<2.0
av>=14.0,<15.0

qdrant-client>=1.17,<2.0
redis>=6.0,<7.0
sqlalchemy>=2.0,<3.0
aiosqlite>=0.20,<1.0

apscheduler>=3.11,<4.0
croniter>=6.0,<7.0

prometheus-client>=0.22,<1.0
opentelemetry-api>=1.33,<2.0
opentelemetry-sdk>=1.33,<2.0
opentelemetry-instrumentation-fastapi>=0.61b0,<1.0

ffmpeg-python>=0.2,<1.0
moviepy>=2.1,<3.0
mutagen>=1.47,<2.0

PyYAML>=6.0,<7.0
rich>=14.0,<15.0
typer>=0.16,<1.0
```

## System dependencies you should install outside pip

These are not Python packages, but your audio and media stack will likely need them in the environment:

* `ffmpeg`
* system audio backends for your OS
* codec support for live audio workflows
* in some cases build tools for `av` and `aiortc`

That part is where many projects discover the ancient truth that “pip install” is not a religion, just one layer of the stack.

## Recommended script creation dependency map

This is the order I would personally use for NOESIS:

1. `settings.py`
2. `noesislogger.py`, `logging.py`, `errors.py`, `validators.py`
3. `schemas.py`, `events.py`, `session.py`
4. `json_store.py`, `session_store.py`
5. `container.py`
6. `event_bus.py`, `task_manager.py`, `lifecycle.py`
7. `openai_client.py`
8. `discord_bot.py`, `x_client.py`
9. `session_service.py`, `platform_service.py`, `voice_service.py`
10. `input_stream.py`, `transcription.py`, `tts_pipeline.py`
11. `conversation_manager.py`, `decision_engine.py`, `response_planner.py`
12. `solo_host_mode.py`, `cohost_manager.py`, `guest_mode.py`
13. `room_moderator.py`, `speaker_queue.py`
14. `live_show.py`, `post_show.py`
15. `publisher_service.py`, `summary_service.py`, `analytics_service.py`
16. tests

That order keeps each script born into a world where its dependencies already exist, which is much nicer than creating orphan files and praying architecture will happen later.

The next clean move is for me to turn this into a **script-by-script build plan** where I list every file, its imports, what classes/functions it should contain, and what other modules it depends on.

[1]: https://developers.openai.com/api/docs/guides/realtime/?utm_source=chatgpt.com "Realtime API"
[2]: https://pypi.org/project/qdrant-client/?utm_source=chatgpt.com "qdrant-client"
[3]: https://pypi.org/project/fastapi/?utm_source=chatgpt.com "fastapi · PyPI"
[4]: https://pypi.org/project/openai/?utm_source=chatgpt.com "OpenAI Python API library"
[5]: https://pypi.org/project/discord.py/?utm_source=chatgpt.com "discord.py"
[6]: https://pypi.org/project/aiortc/?utm_source=chatgpt.com "aiortc"
