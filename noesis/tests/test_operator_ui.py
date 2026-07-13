from pathlib import Path

from fastapi.testclient import TestClient

from noesis_agent.api.app import app


def test_operator_page_and_asset_load_without_credentials() -> None:
    client = TestClient(app)
    root = client.get("/", follow_redirects=False)
    assert root.status_code == 307
    assert root.headers["location"] == "/operator"
    page = client.get("/operator")
    assert page.status_code == 200
    assert "Noesis Operator" in page.text
    assert "No live message will be sent" in page.text
    assert client.get("/operator/assets/logo.png").status_code == 200
    assert client.get("/favicon.ico", follow_redirects=False).headers["location"] == "/operator/assets/noesis_logo.png"


def test_operator_status_is_safe_and_does_not_expose_secret_values(monkeypatch) -> None:
    from noesis_agent.config.settings import settings
    monkeypatch.setattr(settings, "discord_bot_token", "discord-secret-sentinel")
    monkeypatch.setattr(settings, "openai_api_key", "openai-secret-sentinel")
    payload = TestClient(app).get("/operator/status").text
    assert "discord-secret-sentinel" not in payload
    assert "openai-secret-sentinel" not in payload
    assert '"discord_token_present":true' in payload
    assert '"data_path"' not in payload
    assert str(settings.data_dir).replace("\\", "\\\\") not in payload


def test_operator_cognition_inspector_uses_local_nlp_without_provider() -> None:
    response = TestClient(app).post("/operator/cognition/inspect", json={
        "event_id": "operator-cognition-1", "platform": "local",
        "text": "@Noesis feature request: add a memory viewer", "mentioned": True,
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["interpretation"]["intent"] == "feature_request"
    assert payload["interpretation"]["confidence"] >= 0.8
    assert payload["response"]["responder"] == "local-fallback"


def test_operator_plan_and_referenced_logo_exist() -> None:
    assert Path("docs/NOESIS_OPERATOR_GUI_PLAN.md").is_file()
    assert Path("logo/noesis_logo.png").is_file()
