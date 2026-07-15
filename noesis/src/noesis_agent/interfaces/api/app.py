from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from noesis_agent.domain.contracts.planning import EpisodePlan, EpisodePlanRequest
from noesis_agent.domain.contracts.persona import HostReplyRequest, HostReplyResponse
from noesis_agent.domain.contracts.live import HostTurnRequest, HostTurnResult, LiveEventIngestionResult, LiveSessionEventRequest
from noesis_agent.domain.contracts.media import PostShowArtifacts, SessionSummary
from noesis_agent.domain.contracts.voice import RealtimeVoiceTokenRequest as RealtimeTokenRequest
from noesis_agent.domain.contracts.voice import RealtimeVoiceTokenResponse as RealtimeTokenResponse
from noesis_agent.domain.contracts.session import SessionCreateRequest, SessionState
from noesis_agent.domain.entities.transcript import SessionTranscriptEvent, TranscriptEvent
from noesis_agent.domain.contracts.platforms import XPostRequest
from noesis_agent.domain.contracts.mentions import MentionDispatchResult, MentionEvent, MentionResponse
from noesis_agent.integrations.mention_normalizers import normalize_discord_message, normalize_x_mention
from noesis_agent.runtime.container import get_container
from noesis_agent.interfaces.api.operator import router as operator_router

app = FastAPI(title="NOESIS Agent", version="0.1.0")
app.include_router(operator_router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/operator", status_code=307)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> RedirectResponse:
    return RedirectResponse(url="/operator/assets/noesis_logo.png", status_code=307)


class RawMentionTestRequest(BaseModel):
    platform: str
    event: dict = Field(default_factory=dict)
    bot_user_id: str | None = None
    bot_name_or_handle: str = "Noesis"


@app.post("/events/mention/test", response_model=MentionResponse)
async def test_mention(payload: MentionEvent) -> MentionResponse:
    return await get_container().mentions.handle(payload, dry_run=True)


@app.post("/respond/dry-run", response_model=MentionResponse)
async def respond_dry_run(payload: MentionEvent) -> MentionResponse:
    return await get_container().mentions.handle(payload, dry_run=True)


@app.post("/events/mention/raw/test", response_model=MentionDispatchResult)
async def test_raw_mention(payload: RawMentionTestRequest) -> MentionDispatchResult:
    if payload.platform == "discord":
        event = normalize_discord_message(
            payload.event, bot_user_id=payload.bot_user_id,
            bot_name=payload.bot_name_or_handle,
        )
    elif payload.platform == "x":
        event = normalize_x_mention(payload.event, handle=payload.bot_name_or_handle)
    else:
        raise HTTPException(status_code=400, detail="platform must be 'discord' or 'x'")
    return await get_container().mention_dispatcher.dispatch(event, live=False)


@app.get("/health")
def health() -> dict:
    container = get_container()
    health_payload = container.is_healthy()
    return {"status": "ok", "service": "noesis-agent", **health_payload}


@app.get("/state")
def service_state() -> dict:
    container = get_container()
    return {
        "service": "noesis-agent",
        "health": container.is_healthy(),
    }


@app.post("/plans", response_model=EpisodePlan)
async def create_plan(payload: EpisodePlanRequest) -> EpisodePlan:
    container = get_container()
    plan = await container.planner.create_plan(payload)
    container.store.write("plans", plan.plan_id, plan.model_dump(mode="json"))
    return plan


@app.post("/sessions", response_model=SessionState)
def create_session(payload: SessionCreateRequest) -> SessionState:
    return get_container().sessions.create_session(payload)


@app.get("/sessions", response_model=list[SessionState])
def list_sessions(active_only: bool = False) -> list[SessionState]:
    return get_container().sessions.list_sessions(active_only=active_only)


@app.post("/sessions/{session_id}/start", response_model=SessionState)
def start_session(session_id: str) -> SessionState:
    try:
        return get_container().sessions.start_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/sessions/{session_id}/end", response_model=SessionState)
def end_session(session_id: str) -> SessionState:
    try:
        return get_container().sessions.end_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/sessions/{session_id}/events", response_model=LiveEventIngestionResult)
def ingest_session_event(session_id: str, payload: LiveSessionEventRequest) -> LiveEventIngestionResult:
    try:
        return get_container().live_sessions.ingest_event(session_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/sessions/{session_id}/turn", response_model=HostTurnResult)
async def execute_host_turn(session_id: str, payload: HostTurnRequest) -> HostTurnResult:
    try:
        return await get_container().host_runtime.execute_turn(session_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/sessions/{session_id}/transcript", response_model=SessionState)
def add_transcript(session_id: str, payload: SessionTranscriptEvent) -> SessionState:
    try:
        normalized = payload.model_copy(update={"session_id": session_id})
        return get_container().sessions.add_transcript_event(session_id, normalized)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/sessions/{session_id}/transcript", response_model=list[TranscriptEvent])
def get_transcript(session_id: str) -> list[TranscriptEvent]:
    try:
        return get_container().sessions.get_session(session_id).transcript
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/sessions/{session_id}", response_model=SessionState)
def get_session(session_id: str) -> SessionState:
    try:
        return get_container().sessions.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/host/reply", response_model=HostReplyResponse)
async def host_reply(payload: HostReplyRequest) -> HostReplyResponse:
    container = get_container()
    try:
        session = container.sessions.get_session(payload.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    transcript_tail = "\n".join(event.text for event in session.transcript[-8:])
    return await container.host.generate_reply(
        payload,
        transcript_tail,
        session_title=session.title,
        session_id=session.session_id,
    )


@app.post("/sessions/{session_id}/summary", response_model=SessionSummary)
async def build_summary(session_id: str) -> SessionSummary:
    container = get_container()
    try:
        session = container.sessions.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    transcript_text = "\n".join(f"{event.speaker}: {event.text}" for event in session.transcript)
    summary = await container.summary.build_summary(session.session_id, session.title, transcript_text)
    container.store.write("summaries", summary.session_id, summary.model_dump(mode="json"))
    return summary


@app.get("/sessions/{session_id}/summary", response_model=SessionSummary)
async def get_summary(session_id: str) -> SessionSummary:
    container = get_container()
    data = container.store.read("summaries", session_id)
    if data:
        return SessionSummary.model_validate(data)
    return await build_summary(session_id)


@app.get("/sessions/{session_id}/artifacts", response_model=PostShowArtifacts)
async def get_post_show_artifacts(session_id: str) -> PostShowArtifacts:
    container = get_container()
    try:
        session = container.sessions.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    artifacts = await container.post_show.generate(session)
    container.store.write("artifacts", session_id, artifacts.model_dump(mode="json"))
    return artifacts


@app.post("/x/post")
def publish_x_post(payload: XPostRequest) -> dict:
    return get_container().publisher.publish_x_post(payload)


@app.post("/sessions/{session_id}/publish")
async def publish_summary(session_id: str, dry_run: bool = True) -> list[dict]:
    container = get_container()
    data = container.store.read("summaries", session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Summary not found")

    summary = SessionSummary(**data)
    return await container.social.publish_summary_thread(summary, dry_run=dry_run)


@app.post("/realtime/session", response_model=RealtimeTokenResponse)
async def create_realtime_session(payload: RealtimeTokenRequest) -> RealtimeTokenResponse:
    realtime_payload = await get_container().openai.create_realtime_session(
        instructions=payload.instructions,
        voice=payload.voice,
    )
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    return RealtimeTokenResponse(
        token=str(realtime_payload.get("token", "disabled")),
        expires_at=expires_at,
        metadata=realtime_payload.get("session_config", {}),
        payload=realtime_payload,
    )
