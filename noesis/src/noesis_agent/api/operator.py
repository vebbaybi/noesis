from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from typing import Literal
import json
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, ConfigDict

from noesis_agent.config.settings import settings
from noesis_agent.services.container import get_container
from noesis_agent.models.mentions import MentionEvent


router = APIRouter()
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOGO_PATH = PROJECT_ROOT / "logo" / "noesis_logo.png"
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}
STARTED_AT = datetime.now(timezone.utc)
CONFIG_AUDIT: list[dict] = []
OBSERVATION_MODES = {
    "disabled", "mentions_only", "observe_authorized", "observe_and_remember",
    "observe_and_moderate", "full_authorized_assistance",
}


class OperatorConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observation_mode: Literal["disabled", "mentions_only", "observe_authorized",
                              "observe_and_remember", "observe_and_moderate",
                              "full_authorized_assistance"] | None = None
    ambient_response_enabled: bool | None = None
    moderation_analysis_enabled: bool | None = None
    discord_observation_overrides: dict[str, Literal["disabled", "mentions_only", "observe_authorized",
                                                       "observe_and_remember", "observe_and_moderate",
                                                       "full_authorized_assistance"]] | None = None
    confirm: bool = False


def _safe_configuration() -> dict:
    try:
        overrides = json.loads(settings.discord_observation_overrides_raw or "{}")
    except (TypeError, ValueError):
        overrides = {}
    return {
        "observation_mode": settings.memory_observation_mode,
        "ambient_response_enabled": settings.ambient_response_enabled,
        "moderation_analysis_enabled": settings.moderation_analysis_enabled,
        "discord_observation_overrides": overrides,
    }


def _require_local(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host not in LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail="The operator interface is local-only.")


@router.get("/operator", response_class=HTMLResponse, include_in_schema=False)
def operator_page(request: Request) -> HTMLResponse:
    _require_local(request)
    return HTMLResponse(OPERATOR_HTML)


@router.get("/operator/assets/noesis_logo.png", include_in_schema=False)
def operator_logo(request: Request):
    _require_local(request)
    if not LOGO_PATH.is_file():
        raise HTTPException(status_code=404, detail="Operator logo asset is unavailable.")
    return FileResponse(LOGO_PATH, media_type="image/png")


@router.get("/operator/assets/logo.png", include_in_schema=False)
def operator_logo_compat(request: Request):
    return operator_logo(request)


@router.get("/operator/status", include_in_schema=False)
def operator_status(request: Request) -> dict:
    _require_local(request)
    health = get_container().is_healthy()
    storage_available = settings.data_dir.exists()
    storage_writable = storage_available and os.access(settings.data_dir, os.W_OK)
    issues = settings.validate_environment()
    return {
        "service": "noesis-agent",
        "runtime_profile": settings.runtime_profile.name,
        "state": "degraded" if issues else "ready",
        "uptime_seconds": max(0, int((datetime.now(timezone.utc) - STARTED_AT).total_seconds())),
        "storage": {"label": "local_data", "configured": True,
                    "available": storage_available, "writable": storage_writable},
        "providers": health.get("cognition", []),
        "memory": get_container().memory.scoped.health(),
        "local_model": {"state": "not_configured", "required": False,
                        "hardware_profile": _hardware_profile()},
        "features": {
            "discord_enabled": settings.enable_discord,
            "discord_token_present": bool(settings.discord_bot_token),
            "discord_live_send_enabled": bool(
                settings.enable_live_mention_send and settings.enable_discord_mention_send
            ),
            "x_enabled": settings.enable_x,
            "x_write_credentials_complete": all((settings.x_api_key, settings.x_api_secret,
                                                  settings.x_access_token, settings.x_access_token_secret)),
            "openai_enabled": bool(settings.openai_api_key),
            "local_fallback_available": True,
            "observation_mode": settings.memory_observation_mode,
        },
        "configuration_issues": [
            {"key": issue.key, "severity": issue.severity, "detail": issue.message}
            for issue in issues
        ],
    }


@router.post("/operator/cognition/inspect", include_in_schema=False)
async def inspect_cognition(request: Request, event: MentionEvent) -> dict:
    _require_local(request)
    response = await get_container().mentions.handle(event, dry_run=True)
    return {
        "event_id": response.event_id,
        "platform": response.platform,
        "interpretation": response.metadata.get("local_interpretation", {}),
        "authorization": {"state": "simulated_local_dry_run", "mutated_memory": False},
        "scope": {"platform": event.platform, "guild_id": event.metadata.get("guild_id"),
                  "channel_id": event.channel_id, "conversation_id": event.conversation_id},
        "memory": response.metadata.get("memory", {}),
        "moderation": response.metadata.get("moderation"),
        "intervention": response.metadata.get("intervention", {}),
        "capability_route": response.metadata.get("capability_route", {}),
        "response": {"status": response.status, "intent": response.intent,
                     "responder": response.responder, "text": response.text,
                     "limitations": response.missing_capabilities},
    }


@router.get("/operator/memory", include_in_schema=False)
def operator_memory(request: Request, limit: int = 6) -> dict:
    _require_local(request)
    container = get_container()
    return {**container.memory.scoped.operator_summary(preview_limit=limit),
            "worker": container.memory.autonomous.health()}


@router.get("/operator/activity", include_in_schema=False)
def operator_activity(request: Request) -> dict:
    _require_local(request)
    sessions = get_container().sessions.list_sessions(active_only=False)
    active = [session for session in sessions if str(getattr(session, "status", "")) == "active"]
    return {
        "active_sessions": len(active), "total_sessions": len(sessions),
        "recent_sessions": [{
            "id": session.session_id, "title": session.title,
            "status": str(session.status), "platform": str(getattr(session, "platform", "local")),
        } for session in sessions[-8:][::-1]],
    }


@router.get("/operator/capabilities", include_in_schema=False)
def operator_capabilities(request: Request, offset: int = 0, limit: int = 50) -> dict:
    _require_local(request)
    registry = get_container().capabilities
    start = max(0, offset)
    bounded = max(1, min(limit, 100))
    return {"summary": registry.summary(), "offset": start, "limit": bounded,
            "items": [item.safe_dict() for item in registry.capabilities[start:start + bounded]]}


@router.get("/operator/ambient", include_in_schema=False)
def operator_ambient(request: Request) -> dict:
    _require_local(request)
    container = get_container()
    mention_health = container.mentions.health()
    memory_health = container.memory.autonomous.health()
    return {
        "observation_mode": settings.memory_observation_mode,
        "ambient_response_enabled": settings.ambient_response_enabled,
        "moderation_analysis_enabled": settings.moderation_analysis_enabled,
        "enabled_platforms": {"discord": settings.enable_discord, "x": settings.enable_x},
        "allowed_discord_channel_ids": [str(value) for value in settings.discord_allowed_text_channel_ids],
        **mention_health,
        "moderation_signals": memory_health["moderation_signals"],
        "moderator_alerts": memory_health["moderator_alerts"],
        "queue": {key: memory_health[key] for key in ("state", "queue_capacity", "queue_depth",
                                                       "in_flight", "workers", "accepting_work")},
        "recent_moderation": memory_health["recent_moderation"],
        "false_positive_feedback": 0,
    }


@router.get("/operator/configuration", include_in_schema=False)
def operator_configuration(request: Request) -> dict:
    _require_local(request)
    return {"configuration": _safe_configuration(), "audit": CONFIG_AUDIT[-20:]}


@router.post("/operator/configuration", include_in_schema=False)
def update_operator_configuration(request: Request, update: OperatorConfigUpdate) -> dict:
    _require_local(request)
    if not update.confirm:
        raise HTTPException(status_code=409, detail="Confirm the configuration change before applying it.")

    requested = update.model_dump(exclude={"confirm"}, exclude_none=True)
    if not requested:
        raise HTTPException(status_code=400, detail="No configuration changes were supplied.")
    previous = _safe_configuration()
    if "observation_mode" in requested:
        settings.memory_observation_mode = requested["observation_mode"]
    if "ambient_response_enabled" in requested:
        settings.ambient_response_enabled = requested["ambient_response_enabled"]
    if "moderation_analysis_enabled" in requested:
        settings.moderation_analysis_enabled = requested["moderation_analysis_enabled"]
    if "discord_observation_overrides" in requested:
        settings.discord_observation_overrides_raw = json.dumps(
            requested["discord_observation_overrides"], sort_keys=True, separators=(",", ":")
        )

    issues = settings.validate_environment()
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        settings.memory_observation_mode = previous["observation_mode"]
        settings.ambient_response_enabled = previous["ambient_response_enabled"]
        settings.moderation_analysis_enabled = previous["moderation_analysis_enabled"]
        settings.discord_observation_overrides_raw = json.dumps(previous["discord_observation_overrides"])
        raise HTTPException(status_code=422, detail=[
            {"key": issue.key, "detail": issue.message} for issue in errors
        ])

    changed = sorted(key for key in requested if previous.get(key) != _safe_configuration().get(key))
    audit_entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "source": "local_operator",
        "changed_fields": changed,
    }
    CONFIG_AUDIT.append(audit_entry)
    del CONFIG_AUDIT[:-100]
    return {"applied": True, "configuration": _safe_configuration(), "audit": audit_entry,
            "warnings": [{"key": issue.key, "detail": issue.message}
                         for issue in issues if issue.severity != "error"]}


def _hardware_profile() -> str:
    memory_gib = 0.0
    try:
        import psutil
        memory_gib = psutil.virtual_memory().total / 1024 ** 3
    except Exception:
        pass
    if memory_gib < 8 or (os.cpu_count() or 1) <= 2:
        return "deterministic_only"
    return "cpu_compact" if memory_gib < 16 else "cpu_balanced"


LEGACY_OPERATOR_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Noesis Operator</title><style>
:root{color-scheme:dark;--bg:#050817;--panel:#0c1530;--cyan:#3cdcf2;--blue:#2457ff;--muted:#9db0d1}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#102657,var(--bg) 48%);color:#eef7ff;font:15px system-ui,sans-serif}
main{max-width:1050px;margin:auto;padding:32px}.brand{display:flex;align-items:center;gap:18px}.brand img{width:88px;height:88px;object-fit:contain}
h1{margin:0;font-size:2rem}.muted{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;margin-top:24px}
section{background:color-mix(in srgb,var(--panel) 92%,transparent);border:1px solid #21477b;border-radius:16px;padding:20px}label{display:block;margin:12px 0 6px}
textarea,select{width:100%;background:#050b1d;color:white;border:1px solid #31598c;border-radius:9px;padding:10px}button{margin-top:12px;background:linear-gradient(90deg,var(--blue),var(--cyan));border:0;border-radius:9px;padding:10px 15px;font-weight:700;cursor:pointer}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#050b1d;padding:12px;border-radius:9px;min-height:70px}a{color:var(--cyan)}
</style></head><body><main>
<div class="brand"><img src="/operator/assets/noesis_logo.png" alt="The 1807 shark logo"><div><h1>Noesis Operator</h1><div class="muted">Local control and dry-run verification surface</div></div></div>
<nav aria-label="Operator sections"><a href="#overview">Overview</a> · <a href="#cognition">Cognition</a> · <span class="muted">Models · Memory · Sources · Audit (read-only status; controls planned)</span></nav>
<div class="grid"><section id="overview"><h2>Runtime readiness</h2><pre id="status">Loading safe status…</pre><button onclick="loadStatus()">Refresh</button></section>
<section><h2>Mention dry run</h2><label for="platform">Platform shape</label><select id="platform"><option>local</option><option>discord</option><option>x</option></select>
<label for="text">Message</label><textarea id="text" rows="5">@Noesis explain what you can do</textarea><button onclick="testMention()">Run dry test</button><pre id="result">No live message will be sent.</pre></section>
<section><h2>Documentation</h2><p><a href="/docs">OpenAPI docs</a></p><p class="muted">Runbook, audit, and roadmap are repository files. Live-send controls are intentionally unavailable here.</p></section></div>
</main><script>
async function loadStatus(){const r=await fetch('/operator/status');document.querySelector('#status').textContent=JSON.stringify(await r.json(),null,2)}
async function testMention(){const platform=document.querySelector('#platform').value,text=document.querySelector('#text').value;const body={event_id:'operator-'+Date.now(),platform,text,mentioned:true};const r=await fetch('/respond/dry-run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});document.querySelector('#result').textContent=JSON.stringify(await r.json(),null,2)}
loadStatus();</script></body></html>"""

OPERATOR_HTML = (Path(__file__).with_name("operator.html")).read_text(encoding="utf-8")


__all__ = ["router"]
