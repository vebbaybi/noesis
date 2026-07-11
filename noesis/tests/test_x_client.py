from __future__ import annotations

from types import SimpleNamespace

from noesis_agent.clients.x_client import XClient
from noesis_agent.config.settings import settings
from noesis_agent.models.schemas import XPostRequest


class FakeResponse:
    def __init__(self, data=None, includes=None) -> None:
        self.data = data
        self.includes = includes or {}


class FakeTweepyClient:
    def __init__(self) -> None:
        self.get_me_calls = 0
        self.last_mentions_user_id = None
        self.last_mentions_params = None

    def get_me(self, user_fields=None) -> FakeResponse:
        self.get_me_calls += 1
        return FakeResponse(data=SimpleNamespace(id="42", username="noesis"))

    def get_users_mentions(self, id, **params) -> FakeResponse:
        self.last_mentions_user_id = id
        self.last_mentions_params = params
        tweets = [
            SimpleNamespace(
                id="200",
                text="newer mention",
                author_id="2",
                created_at="2026-04-06T10:01:00Z",
                conversation_id="20",
            ),
            SimpleNamespace(
                id="100",
                text="older mention",
                author_id="1",
                created_at="2026-04-06T10:00:00Z",
                conversation_id="10",
            ),
        ]
        users = [
            SimpleNamespace(id="1", username="alice", name="Alice"),
            SimpleNamespace(id="2", username="bob", name="Bob"),
        ]
        return FakeResponse(data=tweets, includes={"users": users})


def build_x_client(fake_client=None) -> XClient:
    client = XClient.__new__(XClient)
    client.client = fake_client
    client._authenticated_user_id = None
    client._authenticated_username = None
    return client


def test_x_post_request_accepts_legacy_fields() -> None:
    payload = XPostRequest(content="hello world", reply_to="12345")

    assert payload.text == "hello world"
    assert payload.reply_to_tweet_id == "12345"
    assert payload.dry_run is True


def test_post_thread_keeps_all_posts_in_dry_run(monkeypatch) -> None:
    monkeypatch.setattr(settings, "enable_x", False)
    client = build_x_client()

    results = client.post_thread(["one", "two", "three"], dry_run=True)

    assert len(results) == 3
    assert [result["status"] for result in results] == ["dry_run", "dry_run", "dry_run"]


def test_get_mentions_caches_authenticated_user_and_orders_results(monkeypatch) -> None:
    monkeypatch.setattr(settings, "enable_x", True)
    fake_client = FakeTweepyClient()
    client = build_x_client(fake_client)

    first = client.get_mentions(since_id="50", max_results=10)
    second = client.get_mentions(since_id="50", max_results=10)

    assert fake_client.get_me_calls == 1
    assert fake_client.last_mentions_user_id == "42"
    assert fake_client.last_mentions_params["since_id"] == "50"
    assert [mention["id"] for mention in first] == ["100", "200"]
    assert [mention["author_username"] for mention in second] == ["alice", "bob"]
