import asyncio

from noesis_agent.integrations.discord.client import NoesisDiscordBot
from noesis_agent.interfaces.commands.handler import CommandHandler
from noesis_agent.infrastructure.config.settings import settings
from noesis_agent.runtime.container import get_container


def test_discord_text_prompt_parser_requires_dm_mention_or_prefix() -> None:
    assert NoesisDiscordBot.extract_text_prompt_from_content("hello room") is None
    assert NoesisDiscordBot.extract_text_prompt_from_content("noesis, hello room") == "hello room"
    assert NoesisDiscordBot.extract_text_prompt_from_content("hey noesis what now?") == "what now?"
    assert NoesisDiscordBot.extract_text_prompt_from_content("!noesis status please") == "status please"
    assert (
        NoesisDiscordBot.extract_text_prompt_from_content(
            "<@12345> what do you think?",
            mentioned=True,
            bot_user_id=12345,
        )
        == "what do you think?"
    )
    assert NoesisDiscordBot.extract_text_prompt_from_content("hello in dm", direct_message=True) == "hello in dm"


def test_command_handler_dispatches_discord_chat(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "x_api_key", "")
    monkeypatch.setattr(settings, "x_api_secret", "")
    monkeypatch.setattr(settings, "x_access_token", "")
    monkeypatch.setattr(settings, "x_access_token_secret", "")
    monkeypatch.setattr(settings, "x_bearer_token", "")
    monkeypatch.setattr(settings, "enable_x", False)
    get_container.cache_clear()

    handler = CommandHandler()
    result = asyncio.run(
        handler.handle(
            "chat",
            {
                "text": "Can you hear this text channel?",
                "author": "Tester",
                "channel_id": "123",
                "channel_name": "lab",
            },
        )
    )

    assert result
    assert "Unknown command" not in result
    get_container.cache_clear()


def test_discord_bot_binds_live_agent_through_injected_getter() -> None:
    class LiveAgentStub:
        def __init__(self) -> None:
            self.client = None

        def set_discord_client(self, client) -> None:
            self.client = client

    live_agent = LiveAgentStub()

    async def callback(command_name, payload):
        return "ok"

    async def run_case() -> None:
        bot = NoesisDiscordBot(callback, live_agent_getter=lambda: live_agent)
        bot._bind_live_agent()
        assert live_agent.client is bot
        await bot.close()

    asyncio.run(run_case())
