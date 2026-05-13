import pytest
from fastapi.testclient import TestClient

from noesis_agent.api.app import app
from noesis_agent.config.settings import settings
from noesis_agent.services.container import get_container


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "discord_bot_token", "")
    monkeypatch.setattr(settings, "enable_discord", False)
    monkeypatch.setattr(settings, "x_api_key", "")
    monkeypatch.setattr(settings, "x_api_secret", "")
    monkeypatch.setattr(settings, "x_access_token", "")
    monkeypatch.setattr(settings, "x_access_token_secret", "")
    monkeypatch.setattr(settings, "x_bearer_token", "")
    monkeypatch.setattr(settings, "enable_x", False)
    get_container.cache_clear()

    with TestClient(app) as test_client:
        yield test_client

    get_container.cache_clear()


def test_plan_endpoint_accepts_legacy_platform_names(client: TestClient) -> None:
    response = client.post(
        "/plans",
        json={
            "show_title": "NOESIS Web3 Session",
            "platform": "X Spaces",
            "objective": "Track the NFT market",
            "audience": "Collectors and traders",
            "duration_minutes": 30,
            "topics": [{"title": "NFT Market Update", "angle": "current signals"}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["platform"] == "x"
    assert body["rundown"][0]["segment"] == "NFT Market Update"


def test_session_workflow_supports_reply_summary_and_publish(client: TestClient) -> None:
    session_response = client.post(
        "/sessions",
        json={"plan_id": "plan-123", "title": "Daily NFT Pulse", "platform": "x"},
    )
    session_id = session_response.json()["session_id"]

    start_response = client.post(f"/sessions/{session_id}/start")
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "live"

    transcript_response = client.post(
        f"/sessions/{session_id}/transcript",
        json={"speaker": "guest", "text": "What projects are getting attention today?", "source": "guest"},
    )
    assert transcript_response.status_code == 200
    assert len(transcript_response.json()["transcript"]) == 1

    transcript_get_response = client.get(f"/sessions/{session_id}/transcript")
    assert transcript_get_response.status_code == 200
    assert transcript_get_response.json()[0]["content"] == "What projects are getting attention today?"

    reply_response = client.post(
        "/host/reply",
        json={
            "session_id": session_id,
            "instruction": "Answer with a concise market take.",
            "latest_context": "The room wants a quick overview.",
            "tone": "sharp, witty, clear",
        },
    )
    assert reply_response.status_code == 200
    assert "OpenAI unavailable" in reply_response.json()["response_text"]

    summary_response = client.post(f"/sessions/{session_id}/summary")
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["session_id"] == session_id
    assert summary["headline"] == "Daily NFT Pulse recap"

    publish_response = client.post(f"/sessions/{session_id}/publish")
    assert publish_response.status_code == 200
    published_posts = publish_response.json()
    assert published_posts
    assert published_posts[0]["status"] == "dry_run"

    end_response = client.post(f"/sessions/{session_id}/end")
    assert end_response.status_code == 200
    assert end_response.json()["status"] == "ended"

    state_response = client.get("/state")
    assert state_response.status_code == 200
    assert state_response.json()["service"] == "noesis-agent"


def test_realtime_session_endpoint_returns_disabled_payload_without_openai(client: TestClient) -> None:
    response = client.post(
        "/realtime/session",
        json={"instructions": "Host the room clearly.", "voice": "alloy"},
    )

    assert response.status_code == 200
    assert response.json()["payload"]["error"] == "OpenAI not configured"
