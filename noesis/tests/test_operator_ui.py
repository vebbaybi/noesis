from pathlib import Path

from fastapi.testclient import TestClient

from noesis_agent.interfaces.api.app import app


def test_operator_page_and_asset_load_without_credentials() -> None:
    client = TestClient(app)
    root = client.get("/", follow_redirects=False)
    assert root.status_code == 307
    assert root.headers["location"] == "/operator"
    page = client.get("/operator")
    assert page.status_code == 200
    assert "Noesis Control Center" in page.text
    assert "Try Noesis safely" in page.text
    assert "What needs attention" in page.text
    assert client.get("/operator/assets/logo.png").status_code == 200
    assert client.get("/favicon.ico", follow_redirects=False).headers["location"] == "/operator/assets/noesis_logo.png"


def test_operator_status_is_safe_and_does_not_expose_secret_values(monkeypatch) -> None:
    from noesis_agent.infrastructure.config.settings import settings
    monkeypatch.setattr(settings, "discord_bot_token", "discord-secret-sentinel")
    monkeypatch.setattr(settings, "openai_api_key", "openai-secret-sentinel")
    payload = TestClient(app).get("/operator/status").text
    assert "discord-secret-sentinel" not in payload
    assert "openai-secret-sentinel" not in payload
    assert '"discord_token_present":true' in payload
    assert '"data_path"' not in payload
    assert str((settings.data_dir / "memory" / "noesis_memory.sqlite3").resolve()).replace("\\", "\\\\") in payload


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


def test_operator_memory_and_activity_are_bounded_and_safe() -> None:
    client = TestClient(app)
    memory = client.get("/operator/memory", params={"limit": 2})
    activity = client.get("/operator/activity")
    assert memory.status_code == 200
    assert activity.status_code == 200
    assert len(memory.json()["recent"]) <= 2
    assert {"active", "superseded", "expired", "deleted", "by_type", "recent"} <= memory.json().keys()
    assert {"active_sessions", "total_sessions", "recent_sessions"} <= activity.json().keys()


def test_operator_page_uses_plain_language_not_raw_status_json() -> None:
    page = TestClient(app).get("/operator").text
    assert "CONNECTED PLATFORMS" in page
    assert "Recently remembered" in page
    assert "JSON.stringify(await r.json(),null,2)" not in page


def test_operator_configuration_requires_confirmation_and_keeps_safe_audit(monkeypatch) -> None:
    from noesis_agent.interfaces.api import operator
    from noesis_agent.infrastructure.config.settings import settings

    monkeypatch.setattr(settings, "memory_observation_mode", "mentions_only")
    monkeypatch.setattr(settings, "ambient_response_enabled", False)
    monkeypatch.setattr(settings, "moderation_analysis_enabled", True)
    monkeypatch.setattr(settings, "discord_observation_overrides_raw", "{}")
    operator.CONFIG_AUDIT.clear()
    client = TestClient(app)

    unconfirmed = client.post("/operator/configuration", json={
        "moderation_analysis_enabled": False,
    })
    assert unconfirmed.status_code == 409
    assert settings.moderation_analysis_enabled is True

    applied = client.post("/operator/configuration", json={
        "moderation_analysis_enabled": False, "confirm": True,
    })
    assert applied.status_code == 200
    payload = applied.json()
    assert payload["configuration"]["moderation_analysis_enabled"] is False
    assert payload["audit"]["changed_fields"] == ["moderation_analysis_enabled"]
    assert set(payload["audit"]) == {"at", "source", "changed_fields"}


def test_operator_configuration_rejects_unsafe_combination_and_rolls_back(monkeypatch) -> None:
    from noesis_agent.infrastructure.config.settings import settings

    monkeypatch.setattr(settings, "memory_observation_mode", "mentions_only")
    monkeypatch.setattr(settings, "ambient_response_enabled", False)
    client = TestClient(app)
    response = client.post("/operator/configuration", json={
        "ambient_response_enabled": True, "confirm": True,
    })
    assert response.status_code == 422
    assert settings.memory_observation_mode == "mentions_only"
    assert settings.ambient_response_enabled is False


def test_operator_ambient_status_is_bounded_and_safe() -> None:
    payload = TestClient(app).get("/operator/ambient").json()
    assert {"observation_mode", "ambient_response_enabled", "moderation_analysis_enabled",
            "queue", "recent_moderation", "false_positive_feedback"} <= payload.keys()
    assert len(payload["recent_moderation"]) <= 20


def test_operator_reports_runtime_identity_and_can_force_memory_hygiene() -> None:
    client = TestClient(app)
    status = client.get("/operator/status").json()
    assert status["runtime_identity"]["cognition_build_id"] == "live-cognition-reality-fix-001"
    assert status["runtime_identity"]["git_branch"]
    assert status["runtime_identity"]["source_file_path"].endswith("noesis_agent\\__init__.py") or \
           status["runtime_identity"]["source_file_path"].endswith("noesis_agent/__init__.py")
    assert "discord_bot_token" not in str(status).lower()
    hygiene = client.post("/operator/memory/hygiene")
    assert hygiene.status_code == 200
    assert hygiene.json()["completed"] is True
    assert {"question_shaped_decisions_found", "downgraded"} <= hygiene.json()["result"].keys()
