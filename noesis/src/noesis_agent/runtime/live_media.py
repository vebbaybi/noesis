from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass

import numpy as np
import discord

from noesis_agent.integrations.audio.transcription import StreamingTranscriber, TranscriptionPipeline
from noesis_agent.integrations.audio.tts_pipeline import TTSPipeline
from noesis_agent.cognition.conversation_manager import ConversationManager
from noesis_agent.cognition.decision_engine import DecisionEngine
from noesis_agent.cognition.response_planner import ResponsePlanner
from noesis_agent.domain.contracts.session import Session, SessionPlatformState
from noesis_agent.integrations.discord.space import build_discord_adapter_from_settings
from noesis_agent.shared.noesislogger import NoesisLogger


def _discord_pcm_to_mono_16k(pcm_bytes: bytes, sample_rate: int) -> bytes:
    if not pcm_bytes:
        return b""

    pcm = np.frombuffer(pcm_bytes, dtype=np.int16)
    if pcm.size == 0:
        return b""

    if pcm.size % 2 == 0:
        mono = pcm.reshape(-1, 2).astype(np.float32).mean(axis=1)
    else:
        mono = pcm.astype(np.float32)

    if sample_rate != 16000 and mono.size > 1:
        output_size = max(1, int(mono.size * 16000 / sample_rate))
        source_positions = np.linspace(0.0, 1.0, num=mono.size, endpoint=False)
        target_positions = np.linspace(0.0, 1.0, num=output_size, endpoint=False)
        mono = np.interp(target_positions, source_positions, mono)

    return np.clip(mono, -32768, 32767).astype(np.int16).tobytes()


@dataclass
class LiveSession:
    session: Session
    platform_state: SessionPlatformState


class LiveMediaAgent:
    """Runs the end-to-end media host loop: listen -> understand -> decide -> speak."""

    def __init__(self, *, data_dir, openai_service, host_service=None, memory_service=None) -> None:
        self.logger = NoesisLogger("noesis.live").logger
        self.conversation = ConversationManager()
        self.transcriber = StreamingTranscriber(
            TranscriptionPipeline(model_size="small.en", device="cpu", compute_type="int8")
        )
        self.tts = TTSPipeline(openai_service)
        self.decision_engine = DecisionEngine(self.conversation)

        if memory_service is None:
            from noesis_agent.memory.service import MemoryService
            memory_service = MemoryService(data_dir)
        self.memory = memory_service

        if host_service is None:
            from noesis_agent.cognition.engine import CognitionEngine
            from noesis_agent.infrastructure.persistence.json_store import JsonStore
            from noesis_agent.application.conversation.host import HostService

            store = JsonStore(data_dir)
            cognition_engine = CognitionEngine(
                store=store,
                openai_service=openai_service,
                memory_service=memory_service,
                data_dir=data_dir,
            )
            host_service = HostService(openai_service=openai_service, cognition_engine=cognition_engine)

        self.host_service = host_service
        self.response_planner = ResponsePlanner(self.host_service, self.conversation)
        self.platform = None
        self._tasks: list[asyncio.Task] = []
        self._session_id: str | None = None
        self._transcript_queue: asyncio.Queue | None = None
        self._discord_client: discord.Client | None = None
        self._last_speaker: str | None = None

    def set_discord_client(self, client: discord.Client) -> None:
        self._discord_client = client

    async def start_autonomous_session(self, topic: str = "Open conversation") -> LiveSession:
        self._ensure_platform()
        platform_state = SessionPlatformState(platform="discord", status="live")
        session = Session(
            plan_id="live",
            title=topic,
            platforms=[platform_state],
            status="live",
        )
        self._session_id = session.session_id
        await self._boot_io()
        await self.platform.join(session_id=session.session_id)  # type: ignore[union-attr]
        self.logger.info("Live session started", extra={"session_id": session.session_id, "topic": topic})
        return LiveSession(session=session, platform_state=platform_state)

    async def speak_text(self, text: str, *, topic: str = "Voice test") -> str:
        message = text.strip()
        if not message:
            return "Voice test text is required."

        if not self._session_id:
            await self.start_autonomous_session(topic=topic)
        else:
            self._ensure_platform()
            await self._boot_io()
            await self.platform.join(session_id=self._session_id)  # type: ignore[union-attr]

        await self.platform.send_text(message[:1800])  # type: ignore[union-attr]

        try:
            audio = await self.tts.synthesize(message)
        except Exception as exc:
            self.logger.warning("Discord voice test could not synthesize TTS", extra={"error": str(exc)})
            return f"Joined voice and posted text, but TTS could not speak: {exc}"

        await self.platform.send_audio(audio)  # type: ignore[union-attr]
        return "Voice test sent to the configured Discord voice channel."

    def _ensure_platform(self) -> None:
        if self.platform is None:
            self.platform = build_discord_adapter_from_settings(client=self._discord_client)

    async def _boot_io(self) -> None:
        self.platform.register_audio_consumer(self._on_audio_frame)
        if self._transcript_queue is None:
            self._transcript_queue = self.transcriber.add_listener()
        if not any(t.get_name() == "transcriber" for t in self._tasks):
            self._tasks.append(asyncio.create_task(self.transcriber.run(), name="transcriber"))
        if not any(t.get_name() == "transcript-consumer" for t in self._tasks):
            self._tasks.append(asyncio.create_task(self._transcript_consumer_loop(), name="transcript-consumer"))
        if not any(t.get_name() == "decision-loop" for t in self._tasks):
            self._tasks.append(asyncio.create_task(self._decision_loop(), name="decision-loop"))

    async def _on_audio_frame(self, pcm_bytes: bytes, sample_rate: int, speaker_name: str | None) -> None:
        if speaker_name:
            self._last_speaker = speaker_name
            self.conversation._update_speakers(speaker_name)

        normalized = _discord_pcm_to_mono_16k(pcm_bytes, sample_rate)
        if normalized:
            await self.transcriber.push_audio(normalized)

    async def _transcript_consumer_loop(self) -> None:
        if self._transcript_queue is None:
            self._transcript_queue = self.transcriber.add_listener()

        while True:
            segments = await self._transcript_queue.get()
            speaker = self._last_speaker or "unknown"
            events = await self.conversation.ingest_segments(
                session_id=self._session_id or "live",
                segments=segments,
                speaker=speaker,
                platform="discord",
            )
            self.memory.working.add(events)
            self.memory.episodic.append(self._session_id or "live", events)

    async def _decision_loop(self) -> None:
        while True:
            await asyncio.sleep(2.0)
            if not self._session_id:
                continue
            decision = self.decision_engine.decide()
            if decision.action in {"wait", "no_events_yet"}:
                continue
            planned = await self.response_planner.plan(decision, session_id=self._session_id)
            if not planned:
                continue
            await self.platform.send_text(planned.text[:1800])
            try:
                audio = await self.tts.synthesize(planned.text)
            except Exception as exc:
                self.logger.warning("Skipping Discord TTS playback", extra={"error": str(exc)})
                continue
            await self.platform.send_audio(audio)

    async def run(self) -> None:
        # Passive loop for background manager; waits forever
        await asyncio.Event().wait()

    async def shutdown(self) -> None:
        with suppress(Exception):
            await self.transcriber.stop()

        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        if self.platform is not None:
            await self.platform.leave()
        self.logger.info("Live agent shut down")
