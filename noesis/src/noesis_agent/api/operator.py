from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from noesis_agent.config.settings import settings
from noesis_agent.services.container import get_container


router = APIRouter()
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOGO_PATH = PROJECT_ROOT / "logo" / "noesis_logo.png"
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


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


@router.get("/operator/status", include_in_schema=False)
def operator_status(request: Request) -> dict:
    _require_local(request)
    health = get_container().is_healthy()
    issues = settings.validate_environment()
    return {
        "service": "noesis-agent",
        "runtime_profile": settings.runtime_profile.name,
        "data_path": str(settings.data_dir),
        "providers": health.get("cognition", []),
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
        },
        "configuration_issues": [
            {"key": issue.key, "severity": issue.severity, "detail": issue.message}
            for issue in issues
        ],
    }


OPERATOR_HTML = """<!doctype html>
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
<div class="grid"><section><h2>Runtime readiness</h2><pre id="status">Loading safe status…</pre><button onclick="loadStatus()">Refresh</button></section>
<section><h2>Mention dry run</h2><label for="platform">Platform shape</label><select id="platform"><option>local</option><option>discord</option><option>x</option></select>
<label for="text">Message</label><textarea id="text" rows="5">@Noesis explain what you can do</textarea><button onclick="testMention()">Run dry test</button><pre id="result">No live message will be sent.</pre></section>
<section><h2>Documentation</h2><p><a href="/docs">OpenAPI docs</a></p><p class="muted">Runbook, audit, and roadmap are repository files. Live-send controls are intentionally unavailable here.</p></section></div>
</main><script>
async function loadStatus(){const r=await fetch('/operator/status');document.querySelector('#status').textContent=JSON.stringify(await r.json(),null,2)}
async function testMention(){const platform=document.querySelector('#platform').value,text=document.querySelector('#text').value;const body={event_id:'operator-'+Date.now(),platform,text,mentioned:true};const r=await fetch('/respond/dry-run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});document.querySelector('#result').textContent=JSON.stringify(await r.json(),null,2)}
loadStatus();</script></body></html>"""


__all__ = ["router"]
