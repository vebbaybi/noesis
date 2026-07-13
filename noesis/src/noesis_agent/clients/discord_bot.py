from __future__ import annotations

import asyncio
import re
from typing import Any, Awaitable, Callable

import discord

from noesis_agent.config.settings import settings
from noesis_agent.platforms.discord_authorization import authorize_discord_message
from noesis_agent.utils.errors import ConfigurationError, handle_noesis_error
from noesis_agent.utils.noesislogger import get_noesis_logger


logger = get_noesis_logger(__name__)
CommandCallback = Callable[[str, dict[str, str]], Awaitable[str | None]]
MentionCallback = Callable[[Any, Any], Awaitable[Any]]


class NoesisDiscordBot(discord.Bot):
    def __init__(self, command_callback: CommandCallback, live_agent_getter: Callable[[], Any] | None = None,
                 mention_callback: MentionCallback | None = None) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True
        intents.voice_states = True
        super().__init__(intents=intents)

        self.command_callback = command_callback
        self.live_agent_getter = live_agent_getter
        self.mention_callback = mention_callback
        self._commands_registered = False
        self._register_commands()

    def _slash_kwargs(self, *, name: str, description: str) -> dict[str, object]:
        kwargs: dict[str, object] = {"name": name, "description": description}
        guild_id = getattr(settings, "discord_guild_id", None)
        if guild_id:
            kwargs["guild_ids"] = [int(guild_id)]
        return kwargs

    async def _respond(self, ctx: discord.ApplicationContext, text: str) -> None:
        message = (text or "Done.")[:2000]
        if ctx.response.is_done():
            await ctx.followup.send(message)
        else:
            await ctx.respond(message)

    async def _ensure_allowed_channel(self, ctx: discord.ApplicationContext) -> bool:
        allowed = set(getattr(settings, "discord_allowed_text_channel_ids", []) or [])
        channel_id = int(getattr(ctx, "channel_id", 0) or getattr(getattr(ctx, "channel", None), "id", 0) or 0)
        if allowed and channel_id not in allowed:
            await self._respond(ctx, "NOESIS is not enabled in this channel.")
            return False
        return True

    async def _ensure_allowed_message_channel(self, message: discord.Message):
        if message.guild is None:
            decision = authorize_discord_message(message, [])
            return type(decision)(True, "direct_message", "direct_message", decision.context)

        allowed = set(getattr(settings, "discord_allowed_text_channel_ids", []) or [])
        decision = authorize_discord_message(message, allowed)
        if allowed and not decision.allowed:
            context = decision.context
            logger.warning(
                "Discord channel authorization rejected",
                extra={
                    "current_channel_id": context.current_channel_id,
                    "parent_channel_id": context.parent_channel_id,
                    "thread_id": context.thread_id,
                    "guild_id": context.guild_id,
                    "allowed_channel_count": len(allowed),
                    "diagnostic_reason": decision.reason,
                    "channel_type": context.channel_type,
                    "authorization_decision": "rejected",
                },
            )
            if self.user is not None and self.user in getattr(message, "mentions", []):
                await message.reply("NOESIS is not enabled in this channel.", mention_author=False)
            return decision
        return decision if allowed else type(decision)(True, "allowlist_not_configured", "unrestricted", decision.context)

    @staticmethod
    def extract_text_prompt_from_content(
        content: str,
        *,
        mentioned: bool = False,
        direct_message: bool = False,
        bot_user_id: int | None = None,
    ) -> str | None:
        content = str(content or "").strip()
        if not content:
            return None

        if bot_user_id is not None:
            content = content.replace(f"<@{bot_user_id}>", "").replace(f"<@!{bot_user_id}>", "").strip()

        prefixed = bool(re.match(r"^(hey\s+)?noesis[:,\s]+", content, flags=re.IGNORECASE))
        command_prefixed = bool(re.match(r"^!noesis\s+", content, flags=re.IGNORECASE))

        if prefixed:
            content = re.sub(r"^(hey\s+)?noesis[:,\s]+", "", content, count=1, flags=re.IGNORECASE).strip()
        elif command_prefixed:
            content = re.sub(r"^!noesis\s+", "", content, count=1, flags=re.IGNORECASE).strip()
        elif not mentioned and not direct_message:
            return None

        return content or "Say hello and ask what this room needs."

    def _extract_text_prompt(self, message: discord.Message) -> str | None:
        return self.extract_text_prompt_from_content(
            str(getattr(message, "content", "") or ""),
            mentioned=self.user is not None and self.user in getattr(message, "mentions", []),
            direct_message=getattr(message, "guild", None) is None,
            bot_user_id=self.user.id if self.user is not None else None,
        )

    def _bind_live_agent(self) -> None:
        live_agent = self.live_agent_getter() if self.live_agent_getter is not None else None
        if live_agent is not None and hasattr(live_agent, "set_discord_client"):
            live_agent.set_discord_client(self)

    def _register_commands(self) -> None:
        if self._commands_registered:
            return

        @self.slash_command(**self._slash_kwargs(name="noesis_ping", description="Check if NOESIS is alive"))
        async def ping(ctx: discord.ApplicationContext) -> None:
            await self._respond(ctx, "NOESIS online and ready.")

        @self.slash_command(**self._slash_kwargs(name="noesis_chat", description="Talk to NOESIS in text"))
        async def chat(ctx: discord.ApplicationContext, message: str) -> None:
            if not await self._ensure_allowed_channel(ctx):
                return
            await ctx.defer()
            result = await self.command_callback(
                "chat",
                {
                    "text": message,
                    "author": getattr(getattr(ctx, "author", None), "display_name", None)
                    or getattr(getattr(ctx, "author", None), "name", "someone"),
                    "channel_id": str(getattr(ctx, "channel_id", "")),
                    "channel_name": getattr(getattr(ctx, "channel", None), "name", "discord"),
                },
            )
            await self._respond(ctx, result or "I am here.")

        @self.slash_command(**self._slash_kwargs(name="noesis_announce", description="Queue an announcement"))
        async def announce(ctx: discord.ApplicationContext, text: str) -> None:
            if not await self._ensure_allowed_channel(ctx):
                return
            await ctx.defer()
            result = await self.command_callback(
                "announce",
                {
                    "text": text,
                    "channel_id": str(getattr(ctx, "channel_id", "")),
                },
            )
            await self._respond(ctx, result or "Announcement queued.")

        @self.slash_command(**self._slash_kwargs(name="noesis_plan", description="Generate episode or Space plan"))
        async def plan(ctx: discord.ApplicationContext, topic: str) -> None:
            if not await self._ensure_allowed_channel(ctx):
                return
            await ctx.defer()
            result = await self.command_callback("plan_episode", {"topic": topic})
            await self._respond(ctx, result or "Planning started.")

        @self.slash_command(**self._slash_kwargs(name="noesis_solo", description="Start autonomous Discord voice hosting"))
        async def solo(ctx: discord.ApplicationContext, topic: str = "NFT Roundup") -> None:
            if not await self._ensure_allowed_channel(ctx):
                return
            await ctx.defer()
            self._bind_live_agent()
            result = await self.command_callback("start_solo", {"topic": topic})
            await self._respond(ctx, result or f"Solo session on '{topic}' triggered.")

        @self.slash_command(**self._slash_kwargs(name="noesis_voice_test", description="Join voice and speak a test line"))
        async def voice_test(
            ctx: discord.ApplicationContext,
            text: str = "NOESIS voice test is live. If you can hear this, the Discord voice loop is connected.",
        ) -> None:
            if not await self._ensure_allowed_channel(ctx):
                return
            await ctx.defer()
            self._bind_live_agent()
            result = await self.command_callback("voice_test", {"text": text})
            await self._respond(ctx, result or "Voice test triggered.")

        @self.slash_command(**self._slash_kwargs(name="noesis_nft", description="Get quick NFT insight"))
        async def nft_insight(ctx: discord.ApplicationContext, query: str) -> None:
            if not await self._ensure_allowed_channel(ctx):
                return
            await ctx.defer()
            result = await self.command_callback("nft_insight", {"query": query})
            await self._respond(ctx, result or "Fetching insight.")

        @self.slash_command(**self._slash_kwargs(name="noesis_status", description="Show NOESIS runtime status"))
        async def status(ctx: discord.ApplicationContext) -> None:
            await self._respond(ctx, "NOESIS is online. Use /noesis_solo to join the configured voice channel.")

        self._commands_registered = True

    async def on_ready(self) -> None:
        if self.user is None:
            logger.info("Discord bot connected, but user is unavailable")
            return
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="/noesis_solo",
            ),
        )
        guilds = ", ".join(f"{guild.name} ({guild.id})" for guild in self.guilds) or "no guilds"
        logger.info(f"Discord bot logged in as {self.user} (ID: {self.user.id}); guilds: {guilds}")

    async def on_message(self, message: discord.Message) -> None:
        if getattr(getattr(message, "author", None), "bot", False):
            return

        prompt = self._extract_text_prompt(message)
        if not prompt:
            return
        authorization = await self._ensure_allowed_message_channel(message)
        if not authorization.allowed:
            return

        if self.mention_callback is not None:
            from noesis_agent.platforms.mention_normalizers import normalize_discord_message

            event = normalize_discord_message(
                message, bot_user_id=self.user.id if self.user is not None else None,
                bot_name=settings.noesis_name,
                authorization=authorization,
            )
            await self.mention_callback(event, message)
            return

        channel = getattr(message, "channel", None)
        try:
            async with channel.typing():
                result = await self.command_callback(
                    "chat",
                    {
                        "text": prompt,
                        "author": getattr(getattr(message, "author", None), "display_name", None)
                        or getattr(getattr(message, "author", None), "name", "someone"),
                        "channel_id": str(getattr(channel, "id", "")),
                        "channel_name": getattr(channel, "name", "direct-message"),
                    },
                )
        except Exception as exc:
            logger.error("Discord text chat failed", exc_info=exc)
            result = "I heard you, but I hit an internal error while answering."

        response = (result or "I am here.")[:2000]
        try:
            await message.reply(response, mention_author=False)
        except (discord.Forbidden, discord.HTTPException):
            if channel is not None:
                await channel.send(response)

    @handle_noesis_error
    async def start_with_config(self) -> None:
        token = getattr(settings, "discord_bot_token", None)
        if not getattr(settings, "enable_discord", False) or not token:
            logger.info("Discord disabled or no token; skipping")
            return
        await self.start(token)


async def start_discord_bot(command_callback: CommandCallback | None = None) -> None:
    if command_callback is None:
        raise ConfigurationError("A command callback is required to start the Discord bot.")

    bot = NoesisDiscordBot(command_callback)
    await bot.start_with_config()


def run_discord_bot_in_background(command_callback: CommandCallback | None = None) -> asyncio.Task:
    return asyncio.create_task(start_discord_bot(command_callback), name="discord-bot")
