from types import SimpleNamespace

from noesis_agent.cognition.local_nlp import LocalNLP
from noesis_agent.models.mentions import MentionEvent
from noesis_agent.platforms.discord_tools import DiscordContextTool


def test_local_nlp_returns_confidence_topics_serious_mode_and_entities() -> None:
    result = LocalNLP().interpret("@Noesis urgent: our wallet token deploy is broken https://example.test")
    assert result.intent == "bug_report"
    assert result.intent_confidence >= 0.8
    assert "web3" in result.topics and "development" in result.topics
    assert result.urgency > 0.8
    assert result.humor_opportunity == 0.0
    assert result.entities["mentions"] == ["Noesis"]


def test_low_confidence_is_explicit() -> None:
    result = LocalNLP().interpret("perhaps later")
    assert result.requires_clarification
    assert result.intent == "unclear"


def test_authorized_discord_jit_tool_uses_only_current_gateway_metadata() -> None:
    event = MentionEvent(event_id="1", platform="discord", text="@Noesis what server is this?",
                         channel_id="c1", conversation_id="t1", mentioned=True,
                         metadata={"guild_id": "g1", "is_thread": True, "channel_type": "Thread"})
    message = SimpleNamespace(guild=SimpleNamespace(name="Private Lab", member_count=12),
                              channel=SimpleNamespace(name="test-thread", archived=False, locked=False))
    evidence = DiscordContextTool().inspect(event, message, authorized=True)
    assert evidence.facts["member_count"] == 12
    assert evidence.scope["conversation_id"] == "t1"
    assert evidence.tool_name == "discord.current_context"


def test_discord_jit_tool_fails_closed_without_authorization() -> None:
    event = MentionEvent(event_id="1", platform="discord", text="member count", mentioned=True)
    evidence = DiscordContextTool().inspect(event, SimpleNamespace(), authorized=False)
    assert evidence.authorized is False
    assert evidence.facts == {}
    assert evidence.limitation == "authorization_required"
