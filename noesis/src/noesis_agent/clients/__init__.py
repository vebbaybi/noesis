"""Client package exports."""

from __future__ import annotations

__all__ = [
    "OpenAIService",
    "XClient",
    "NoesisDiscordBot",
    "run_discord_bot_in_background",
    "start_discord_bot",
]


def __getattr__(name: str):
    if name == "OpenAIService":
        from .openai_client import OpenAIService

        return OpenAIService

    if name == "XClient":
        from .x_client import XClient

        return XClient

    if name in {"NoesisDiscordBot", "run_discord_bot_in_background", "start_discord_bot"}:
        from .discord_bot import NoesisDiscordBot, run_discord_bot_in_background, start_discord_bot

        exports = {
            "NoesisDiscordBot": NoesisDiscordBot,
            "run_discord_bot_in_background": run_discord_bot_in_background,
            "start_discord_bot": start_discord_bot,
        }
        return exports[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
