from __future__ import annotations

import asyncio
from pathlib import Path

from noesis_agent.capabilities.content import build_local_research_brief, build_local_session_summary, build_summary_thread
from noesis_agent.domain.entities.guest import Guest
from noesis_agent.domain.contracts.platforms import XPostRequest
from noesis_agent.domain.contracts.persona import HostReplyResponse
from noesis_agent.domain.contracts.session import SessionCreateRequest
from noesis_agent.domain.entities.transcript import TranscriptEvent
from noesis_agent.infrastructure.observability.service import AnalyticsService
from noesis_agent.cognition.knowledge.service import ResearchService
from noesis_agent.infrastructure.persistence.guest_store import GuestStore
from noesis_agent.infrastructure.persistence.json_store import JsonStore


class DummyOpenAI:
    def is_enabled(self) -> bool:
        return False


def test_model_split_keeps_legacy_payloads_compatible() -> None:
    request = SessionCreateRequest.model_validate({"plan_id": "plan-1", "platform": "X Spaces"})
    assert request.platforms == ["x"]

    event = TranscriptEvent.model_validate(
        {"session_id": "session-1", "speaker": "guest", "text": "What is the ETH setup?", "source": "guest"}
    )
    assert event.content == "What is the ETH setup?"
    assert event.role == "guest"
    assert event.text == event.content

    reply = HostReplyResponse.model_validate({"response_text": "Keep the downside in view."})
    assert reply.text == "Keep the downside in view."
    assert reply.response_text == reply.text

    post = XPostRequest.model_validate({"content": "NOESIS recap", "reply_to": "123"})
    assert post.text == "NOESIS recap"
    assert post.reply_to_tweet_id == "123"


def test_summary_builder_produces_publishable_thread() -> None:
    transcript = (
        "host: BTC liquidity looked better than sentiment implied.\n"
        "guest: NFT volume is uneven, so conviction still needs risk framing.\n"
        "host: lol the market keeps testing who actually has patience."
    )
    summary = build_local_session_summary("session-1", "Daily Market Pulse", transcript)

    assert summary.headline == "Daily Market Pulse recap"
    assert summary.key_moments
    assert summary.alpha_drops
    assert summary.x_thread
    assert any("DYOR" in post for post in summary.x_thread)

    thread = build_summary_thread(summary, add_finance_disclaimer=True)
    assert len(thread) >= 3


def test_research_builder_and_service_work_offline() -> None:
    brief = build_local_research_brief(
        "ETH market structure",
        raw_text="- Momentum is constructive but invalidation matters.\n- Risk rises if spot demand fades.",
    )
    assert brief.findings
    assert "ETH market structure" in brief.executive_summary

    service = ResearchService(DummyOpenAI())
    insight = asyncio.run(service.quick_insight("ETH market structure"))
    assert insight.startswith("[offline]")


def test_json_store_list_and_guest_store_round_trip(tmp_path: Path) -> None:
    store = JsonStore(tmp_path / "root")
    store.write("items", "one", {"value": 1})
    store.write("items", "two", {"value": 2})

    payloads = store.list("items")
    assert {item["value"] for item in payloads} == {1, 2}

    guest_store = GuestStore(tmp_path)
    guest = Guest(handle="wildf", display_name="Wildf", expertise=["markets"], prior_appearances=2)
    guest_store.save(guest)

    guests = guest_store.list()
    assert len(guests) == 1
    assert guests[0].handle == "wildf"
    assert guests[0].prior_appearances == 2


def test_analytics_service_returns_structured_snapshot() -> None:
    analytics = AnalyticsService()
    analytics.record_listener_count(42)
    analytics.record_message_seen()
    analytics.record_reply_generated()

    snapshot = analytics.snapshot()
    assert snapshot["engagement"]["listeners_last"] == 42
    assert snapshot["engagement"]["messages_seen"] == 1
    assert snapshot["engagement"]["replies_generated"] == 1
