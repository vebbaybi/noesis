from __future__ import annotations

import asyncio
import io
from contextlib import suppress

import discord

from noesis_agent.config.settings import settings
from noesis_agent.platforms.base import AudioCallback
from noesis_agent.utils.errors import ConfigurationError
from noesis_agent.utils.noesislogger import NoesisLogger

SinkBase = getattr(getattr(discord, "sinks", None), "Sink", None)


class _StreamingSink(SinkBase if SinkBase is not None else object):
    """Pycord sink that forwards decoded Discord PCM frames into the agent loop."""

    def __init__(self, callback: AudioCallback, sample_rate: int, loop: asyncio.AbstractEventLoop, logger) -> None:
        if SinkBase is None:
            raise ConfigurationError(
                "Discord voice receive requires Pycord. Install `py-cord[voice]` and remove `discord.py`.",
                missing_key="py-cord[voice]",
            )
        super().__init__(filters=None)
        self.callback = callback
        self.sample_rate = sample_rate
        self.loop = loop
        self.logger = logger

    def write(self, data: bytes, user_id: int) -> None:  # type: ignore[override]
        if not data or self.loop.is_closed():
            return

        speaker_name = self._speaker_name(user_id)
        future = asyncio.run_coroutine_threadsafe(
            self.callback(bytes(data), self.sample_rate, speaker_name),
            self.loop,
        )
        future.add_done_callback(self._log_callback_failure)

    def _speaker_name(self, user_id: int) -> str | None:
        vc = getattr(self, "vc", None)
        guild = getattr(vc, "guild", None)
        if guild is None:
            return str(user_id) if user_id else None

        with suppress(TypeError, ValueError):
            member = guild.get_member(int(user_id))
            if member is not None:
                return getattr(member, "display_name", None) or getattr(member, "name", None)
        return str(user_id) if user_id else None

    def _log_callback_failure(self, future) -> None:
        try:
            future.result()
        except Exception as exc:
            self.logger.error("Discord audio frame callback failed", exc_info=exc)


class DiscordSpaceAdapter:
    """Discord Stage/Voice adapter that streams audio into the agent and plays back TTS."""

    def __init__(
        self,
        *,
        token: str,
        guild_id: int,
        voice_channel_id: int,
        sample_rate: int = 48000,
        client: discord.Client | None = None,
    ) -> None:
        if SinkBase is None:
            raise ConfigurationError(
                "Discord voice receive requires Pycord. Install `py-cord[voice]` and remove `discord.py`.",
                missing_key="py-cord[voice]",
            )

        if client is None:
            intents = discord.Intents.none()
            intents.guilds = True
            intents.voice_states = True
            client = discord.Client(intents=intents)
            self._owns_client = True
        else:
            self._owns_client = False

        self.client = client
        self.token = token
        self.guild_id = guild_id
        self.voice_channel_id = voice_channel_id
        self.sample_rate = sample_rate
        self.logger = NoesisLogger("noesis.platforms.discord").logger
        self.voice_client: discord.VoiceClient | None = None
        self._audio_consumer: AudioCallback | None = None
        self._connect_task: asyncio.Task | None = None
        self._play_lock = asyncio.Lock()

    def register_audio_consumer(self, consumer: AudioCallback) -> None:
        self._audio_consumer = consumer

    async def join(self, *, session_id: str) -> None:
        if not self._audio_consumer:
            raise RuntimeError("Audio consumer must be registered before joining")

        if self._owns_client and not self.client.is_ready():
            await self.client.login(self.token)
            self._connect_task = asyncio.create_task(self.client.connect(reconnect=True), name="discord-voice-client")

        if not self.client.is_ready():
            await asyncio.wait_for(self.client.wait_until_ready(), timeout=60)

        guild = self.client.get_guild(self.guild_id)
        if guild is None:
            raise RuntimeError(f"Guild {self.guild_id} not found")

        channel = self.client.get_channel(self.voice_channel_id) or guild.get_channel(self.voice_channel_id)
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            raise RuntimeError(f"Channel {self.voice_channel_id} is not a voice/stage channel")

        self.voice_client = self._existing_voice_client()
        if self.voice_client and self.voice_client.is_connected():
            if getattr(getattr(self.voice_client, "channel", None), "id", None) != self.voice_channel_id:
                await self.voice_client.move_to(channel)
        else:
            self.voice_client = await channel.connect(self_deaf=False, self_mute=False)

        await self._ensure_stage_speaking(channel)

        if not getattr(self.voice_client, "recording", False):
            sink = _StreamingSink(
                self._audio_consumer,
                self.sample_rate,
                asyncio.get_running_loop(),
                self.logger,
            )
            self.voice_client.start_recording(sink, self._on_recording_finished, sync_start=True)

        self.logger.info(
            "Joined Discord voice channel and started streaming",
            extra={"guild_id": self.guild_id, "channel_id": self.voice_channel_id, "session_id": session_id},
        )

    def _existing_voice_client(self) -> discord.VoiceClient | None:
        for voice_client in getattr(self.client, "voice_clients", []):
            guild = getattr(voice_client, "guild", None)
            if getattr(guild, "id", None) == self.guild_id:
                return voice_client
        return None

    async def _ensure_stage_speaking(self, channel: discord.abc.GuildChannel) -> None:
        if not isinstance(channel, discord.StageChannel):
            return

        guild = self.client.get_guild(self.guild_id)
        member = getattr(guild, "me", None) if guild is not None else None
        if member is None:
            return

        with suppress(discord.HTTPException, discord.Forbidden, AttributeError):
            await member.edit(suppress=False)

    async def _on_recording_finished(self, sink: SinkBase) -> None:
        self.logger.info("Discord recording stopped")

    async def send_text(self, text: str) -> None:
        if not self.client.is_ready():
            return

        guild = self.client.get_guild(self.guild_id)
        if guild is None:
            return

        channel = guild.system_channel
        for channel_id in getattr(settings, "discord_allowed_text_channel_ids", []) or []:
            candidate = self.client.get_channel(int(channel_id))
            if isinstance(candidate, discord.TextChannel):
                channel = candidate
                break

        if channel:
            await channel.send(text[:2000])

    async def send_audio(self, audio_bytes: bytes, *, sample_rate: int = 24000) -> None:
        if not audio_bytes:
            return

        if not self.voice_client or not self.voice_client.is_connected():
            self.logger.warning("Cannot send audio; not connected to voice")
            return

        done = asyncio.Event()
        loop = asyncio.get_running_loop()

        def _after_play(error: Exception | None) -> None:
            if error is not None:
                self.logger.error("Discord audio playback failed", exc_info=error)
            loop.call_soon_threadsafe(done.set)

        audio_source = discord.FFmpegPCMAudio(
            source=io.BytesIO(audio_bytes),
            pipe=True,
            before_options="-f wav -i pipe:0",
            options="-vn -ac 2 -ar 48000",
        )

        async with self._play_lock:
            while self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
                await asyncio.sleep(0.05)

            self.voice_client.play(audio_source, after=_after_play)
            await done.wait()

    async def leave(self) -> None:
        if self.voice_client and self.voice_client.is_connected():
            with suppress(Exception):
                if getattr(self.voice_client, "recording", False):
                    self.voice_client.stop_recording()
            await self.voice_client.disconnect(force=True)

        if self._owns_client:
            await self.client.close()

        self.logger.info("Left Discord voice channel")


def build_discord_adapter_from_settings(client: discord.Client | None = None) -> DiscordSpaceAdapter:
    if not settings.discord_bot_token:
        raise ConfigurationError("DISCORD_BOT_TOKEN not configured", missing_key="DISCORD_BOT_TOKEN")
    if not settings.discord_guild_id:
        raise ConfigurationError("DISCORD_GUILD_ID not configured", missing_key="DISCORD_GUILD_ID")
    if not settings.discord_voice_channel_id:
        raise ConfigurationError("DISCORD_VOICE_CHANNEL_ID not configured", missing_key="DISCORD_VOICE_CHANNEL_ID")

    return DiscordSpaceAdapter(
        token=settings.discord_bot_token,
        guild_id=int(settings.discord_guild_id),
        voice_channel_id=int(settings.discord_voice_channel_id),
        client=client,
    )


__all__ = ["DiscordSpaceAdapter", "build_discord_adapter_from_settings"]
