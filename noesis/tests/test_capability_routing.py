from pathlib import Path

from noesis_agent.cognition.capabilities import CapabilityRegistry


def router():
    return CapabilityRegistry(Path("../assets/users_request.md"))


def test_owner_semantic_variants_route_to_same_capability() -> None:
    routes = [router().route(platform="discord", text=text, intent="question")
              for text in ("Who owns this server?", "Who runs this guild?", "Who is the server owner?")]
    assert {route["matches"][0]["capability_id"] for route in routes} == {"discord.guild.owner"}


def test_creator_and_visible_member_queries_preserve_semantic_limitations() -> None:
    created = router().route(platform="discord", text="Who created this Discord?", intent="question")
    visible = router().route(platform="discord", text="How many people can see this channel?", intent="question")
    assert "original-creator" in created["matches"][0]["limitation"]
    assert visible["matches"][0]["capability_id"] == "discord.channel.visible_members"
