from types import SimpleNamespace

from noesis_agent.cognition.nlu.interpreter import LocalNLP
from noesis_agent.domain.contracts.mentions import MentionEvent
from noesis_agent.integrations.discord.tools import DiscordContextTool


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


def test_discord_owner_and_member_metrics_are_semantically_distinct() -> None:
    guild = SimpleNamespace(id=123456789012345678, name="Sharktank", owner_id=7,
                            owner=SimpleNamespace(display_name="Webbaby"), member_count=42,
                            members=[object(), object()], created_at=None)
    message = SimpleNamespace(guild=guild, channel=SimpleNamespace(
        name="general", topic="Welcome", nsfw=False, slowmode_delay=0))
    event = MentionEvent(event_id="owner", platform="discord", text="Who owns this server?",
                         channel_id="9", conversation_id="9", metadata={
                             "guild_id": str(guild.id), "channel_type": "text", "is_thread": False})
    facts = DiscordContextTool().inspect(event, message, authorized=True).facts
    assert facts["guild_owner_display_name"] == "Webbaby"
    assert facts["member_count"] == 42
    assert facts["cached_member_count"] == 2


def test_channel_visible_members_require_complete_cache_and_permissions() -> None:
    members = [SimpleNamespace(status="online"), SimpleNamespace(status="offline")]
    guild = SimpleNamespace(id=123, name="Guild", owner_id=1, owner=None, member_count=2,
                            members=members, chunked=True, roles=[], features=[],
                            verification_level=None, me=None, created_at=None)
    channel = SimpleNamespace(id=9, name="private", topic=None, nsfw=False, slowmode_delay=0,
                              parent=None, members=[], created_at=None,
                              permissions_for=lambda member: SimpleNamespace(view_channel=member is members[0]))
    event = MentionEvent(event_id="visible", platform="discord",
                         text="How many members does this channel have?", channel_id="9",
                         metadata={"guild_id": "123", "channel_type": "text", "is_thread": False})
    facts = DiscordContextTool().inspect(event, SimpleNamespace(guild=guild, channel=channel,
                                                                 author=None), authorized=True).facts
    assert facts["member_count"] == 2
    assert facts["cached_visible_member_count"] == 1
    assert facts["online_presence_count"] == 1


def test_incomplete_cache_never_substitutes_guild_count_for_channel_visibility() -> None:
    guild = SimpleNamespace(id=123, name="Guild", owner_id=None, owner=None, member_count=50,
                            members=[object()], chunked=False, roles=[], features=[],
                            verification_level=None, me=None, created_at=None)
    channel = SimpleNamespace(id=9, name="private", topic=None, nsfw=False, slowmode_delay=0,
                              parent=None, members=[], created_at=None,
                              permissions_for=lambda member: SimpleNamespace(view_channel=True))
    event = MentionEvent(event_id="limited", platform="discord", text="How many people can see this channel?",
                         channel_id="9", metadata={"guild_id": "123", "channel_type": "text", "is_thread": False})
    facts = DiscordContextTool().inspect(event, SimpleNamespace(guild=guild, channel=channel,
                                                                 author=None), authorized=True).facts
    assert "cached_visible_member_count" not in facts
    assert facts["member_count"] == 50
