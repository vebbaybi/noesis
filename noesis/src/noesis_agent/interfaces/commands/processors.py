from __future__ import annotations

"""Command processors for NOESIS.

Each processor wraps a concrete action that can be triggered via Discord slash
commands, HTTP endpoints, or other control surfaces. The processors are kept
thin and delegate to services exposed through the dependency container so they
remain testable and platform-agnostic.
"""

from typing import Any

from noesis_agent.runtime.container import get_container
from noesis_agent.shared.noesislogger import NoesisLogger


class BaseCommand:
    def __init__(self, logger_name: str) -> None:
        self.logger = NoesisLogger(logger_name).logger
        self.container = get_container()


class AnnounceCommand(BaseCommand):
    def __init__(self) -> None:
        super().__init__("noesis.commands.announce")

    async def execute(self, payload: dict[str, Any]) -> str:
        text = str(payload.get("text", "")).strip()
        platform = str(payload.get("platform", self.container.platform.primary)).lower()

        if not text:
            return "Announcement text is required."

        formatted = await self.container.platform.format_announcement(text, platform=platform)
        self.logger.info(
            "Announcement formatted",
            extra={"platform": platform, "length": len(formatted)},
        )

        # For now we only echo; publishing happens through platform-specific services.
        return formatted


class PlanEpisodeCommand(BaseCommand):
    def __init__(self) -> None:
        super().__init__("noesis.commands.plan_episode")

    async def execute(self, payload: dict[str, Any]) -> str:
        topic = str(payload.get("topic", "Web3 weekly pulse")).strip()
        if not topic:
            return "Please provide a topic for planning."

        from noesis_agent.domain.contracts.planning import EpisodePlanRequest, Topic

        req = EpisodePlanRequest(
            show_title=str(payload.get("show_title", "NOESIS Live Show")),
            platform=payload.get("platform", "dual"),
            objective=payload.get(
                "objective",
                "Host an engaging, fast-paced space with curated guests and live commentary.",
            ),
            target_audience=payload.get("audience", "Crypto + culture listeners"),
            topics=[Topic(title=topic, angle=payload.get("angle", "latest developments"))],
            duration_minutes=int(payload.get("duration_minutes", 45)),
            hosts=payload.get("hosts", []),
            guests=payload.get("guests", []),
            tags=payload.get("tags", []),
        )

        plan = await self.container.planner.create_plan(req)
        self.container.store.write("plans", plan.plan_id, plan.model_dump(mode="json"))

        return (
            f"Plan created: {plan.show_title} ({plan.duration_minutes} min). "
            f"Segments: {len(plan.topics)}. Plan ID: {plan.plan_id[:8]}."
        )


class SoloSessionCommand(BaseCommand):
    def __init__(self) -> None:
        super().__init__("noesis.commands.solo")

    async def execute(self, payload: dict[str, Any]) -> str:
        topic = str(payload.get("topic", "Daily crypto pulse")).strip() or "Daily crypto pulse"

        try:
            session = await self.container.live.start_autonomous_session(topic=topic)
        except Exception as exc:
            self.logger.error("Failed to start solo session", exc_info=exc)
            return f"Could not start live session: {exc}"

        return (
            f"Solo live session started on '{topic}'.\n"
            f"Session ID: {session.session.session_id}. "
            f"Primary platform: {session.session.primary_platform}."
        )


class VoiceTestCommand(BaseCommand):
    def __init__(self) -> None:
        super().__init__("noesis.commands.voice_test")

    async def execute(self, payload: dict[str, Any]) -> str:
        text = str(
            payload.get(
                "text",
                "NOESIS voice test is live. If you can hear this, the Discord voice loop is connected.",
            )
        ).strip()
        if not text:
            text = "NOESIS voice test is live."

        try:
            return await self.container.live.speak_text(text, topic="Discord voice test")
        except Exception as exc:
            self.logger.error("Failed to run Discord voice test", exc_info=exc)
            return f"Could not run voice test: {exc}"


class ChatCommand(BaseCommand):
    def __init__(self) -> None:
        super().__init__("noesis.commands.chat")

    async def execute(self, payload: dict[str, Any]) -> str:
        text = str(payload.get("text", "")).strip()
        if not text:
            return "Say something for NOESIS to respond to."

        author = str(payload.get("author", "someone")).strip() or "someone"
        channel_name = str(payload.get("channel_name", "discord")).strip() or "discord"
        channel_id = str(payload.get("channel_id", "general")).strip() or "general"

        from noesis_agent.domain.contracts.live import HostTurnRequest, LiveEventType, LiveSessionEventRequest, OutputChannel
        from noesis_agent.domain.contracts.session import SessionCreateRequest

        plan_id = f"discord-text-{channel_id}"
        state = next(
            (
                item
                for item in self.container.sessions.list_sessions(active_only=True)
                if item.session.plan_id == plan_id and item.session.status != "ended"
            ),
            None,
        )
        if state is None:
            state = self.container.sessions.create_session(
                SessionCreateRequest(
                    plan_id=plan_id,
                    title=f"Discord #{channel_name}",
                    platform="discord",
                    mode="cohost",
                )
            )
        if state.session.status != "live":
            state = self.container.sessions.start_session(state.session_id)

        result = await self.container.host_runtime.execute_turn(
            state.session_id,
            HostTurnRequest(
                event=LiveSessionEventRequest(
                    event_type=LiveEventType.USER_MESSAGE,
                    speaker=author,
                    role="audience",
                    content=text,
                    platform="discord",
                    metadata={"channel_id": channel_id, "channel_name": channel_name, "source": "discord_text"},
                ),
                output_channels=[OutputChannel.API_RESPONSE_ONLY],
            ),
        )
        return result.host_text or "I heard you, but I do not have a host response ready for that turn."


class NFTInsightCommand(BaseCommand):
    def __init__(self) -> None:
        super().__init__("noesis.commands.nft_insight")

    async def execute(self, payload: dict[str, Any]) -> str:
        query = str(payload.get("query", "trending NFTs")).strip()
        if not query:
            return "Please provide an NFT or project to analyze."

        insight = await self.container.research.quick_insight(query)
        return insight


__all__ = [
    "AnnounceCommand",
    "ChatCommand",
    "PlanEpisodeCommand",
    "SoloSessionCommand",
    "VoiceTestCommand",
    "NFTInsightCommand",
]
