from __future__ import annotations

from functools import lru_cache

from noesis_agent.infrastructure.config.settings import settings


@lru_cache(maxsize=1)
def get_container() -> "ServiceContainer":
    return ServiceContainer()


class ServiceContainer:
    def __init__(self) -> None:
        from noesis_agent.cognition.engine import CognitionEngine
        from noesis_agent.integrations.llm.openai import OpenAIService
        from noesis_agent.integrations.x.client import XClient
        from noesis_agent.cognition.providers import CognitionProviderRouter
        from noesis_agent.application.conversation.host import HostService
        from noesis_agent.application.conversation.runtime import HostRuntimeService
        from noesis_agent.application.conversation.host_decisions import HostDecisionService
        from noesis_agent.application.conversation.live_sessions import LiveSessionService
        from noesis_agent.memory.service import MemoryService
        from noesis_agent.application.mentions.service import MentionService
        from noesis_agent.application.mentions.dispatcher import MentionDispatcher
        from noesis_agent.application.output.adapters import DiscordOutputAdapter, LocalTextOutputAdapter
        from noesis_agent.application.output.router import OutputRouter
        from noesis_agent.capabilities.media.post_show_service import PostShowArtifactService
        from noesis_agent.capabilities.scheduling.planner_service import PlannerService
        from noesis_agent.capabilities.publishing.publisher import PublisherService
        from noesis_agent.cognition.knowledge.service import ResearchService
        from noesis_agent.application.conversation.response_modes import ResponseModeRouter
        from noesis_agent.application.conversation.sessions import SessionService
        from noesis_agent.capabilities.publishing.social import SocialService
        from noesis_agent.capabilities.content.summary_service import SummaryService
        from noesis_agent.capabilities.scheduling.topic_planning_service import TopicPlanningService
        from noesis_agent.application.conversation.transcripts import TranscriptService
        from noesis_agent.infrastructure.persistence.json_store import JsonStore
        from noesis_agent.integrations.discord.tools import DiscordContextTool
        from noesis_agent.cognition.capabilities import CapabilityRegistry

        self.store = JsonStore(settings.data_dir)

        self.openai = OpenAIService()
        self.discord_context_tool = DiscordContextTool()
        catalogue = settings.project_root / "assets" / "users_request.md"
        if not catalogue.is_file():
            catalogue = settings.project_root.parent / "assets" / "users_request.md"
        self.capabilities = CapabilityRegistry(catalogue)
        self.x_client = XClient()
        self.cognition = CognitionProviderRouter.from_settings(self.openai, settings)

        self.memory = MemoryService(settings.data_dir)
        self.mentions = MentionService(self.openai, noesis_name=settings.noesis_name,
                                       autonomous_memory=self.memory.autonomous if settings.autonomous_memory_enabled else None,
                                       observation_mode=settings.memory_observation_mode,
                                       capability_registry=self.capabilities)
        self.mentions.ambient_response_enabled = settings.ambient_response_enabled
        self.mentions.moderation_analysis_enabled = settings.moderation_analysis_enabled
        self.mention_dispatcher = MentionDispatcher(
            self.mentions, runtime_settings=settings, x_client=self.x_client
        )
        self.cognition_engine = CognitionEngine(
            store=self.store,
            openai_service=self.openai,
            memory_service=self.memory,
            data_dir=settings.data_dir,
        )

        self.transcripts = TranscriptService()
        self.topic_planning = TopicPlanningService()
        self.host_decisions = HostDecisionService()
        self.response_modes = ResponseModeRouter(self.transcripts)
        self.sessions = SessionService(store=self.store, transcript_service=self.transcripts)
        self.publisher = PublisherService(x_client=self.x_client)
        self.social = SocialService(publisher_service=self.publisher)
        self.planner = PlannerService(openai_service=self.openai)
        self.host = HostService(
            openai_service=self.openai,
            cognition_engine=self.cognition_engine,
            cognition_provider=self.cognition,
        )
        self.summary = SummaryService(openai_service=self.openai)
        self.post_show = PostShowArtifactService(self.summary, self.transcripts)
        self.live_sessions = LiveSessionService(
            sessions=self.sessions,
            transcripts=self.transcripts,
            memory=self.memory,
            topics=self.topic_planning,
            decisions=self.host_decisions,
            response_router=self.response_modes,
        )
        self.local_output = LocalTextOutputAdapter()
        self.discord_output = DiscordOutputAdapter(
            runtime_settings=settings,
            live_agent_getter=lambda: getattr(self, "_live", None),
        )
        self.output_router = OutputRouter(
            runtime_settings=settings,
            local_adapter=self.local_output,
            discord_adapter=self.discord_output,
        )
        self.host_runtime = HostRuntimeService(
            live_sessions=self.live_sessions,
            cognition=self.cognition,
            sessions=self.sessions,
            transcripts=self.transcripts,
            memory=self.memory,
            output_router=self.output_router,
        )
        self.research = ResearchService(openai_service=self.openai)

        self._platform = None
        self._analytics = None
        self._recording = None
        self._voice = None
        self._moderation = None
        self._live = None

    @property
    def platform(self):
        if self._platform is None:
            from noesis_agent.integrations.service import PlatformService

            self._platform = PlatformService(openai=self.openai)
        return self._platform

    @property
    def analytics(self):
        if self._analytics is None:
            from noesis_agent.infrastructure.observability.service import AnalyticsService

            self._analytics = AnalyticsService()
        return self._analytics

    @property
    def recording(self):
        if self._recording is None:
            from noesis_agent.capabilities.media.recording_service import RecordingService

            self._recording = RecordingService(settings.data_dir / "recordings")
        return self._recording

    @property
    def voice(self):
        if self._voice is None:
            from noesis_agent.integrations.audio.service import VoiceService

            self._voice = VoiceService(self.openai, self.cognition_engine.voice_profiles)
        return self._voice

    @property
    def moderation(self):
        if self._moderation is None:
            from noesis_agent.capabilities.moderation.service import ModerationService

            self._moderation = ModerationService()
        return self._moderation

    @property
    def live(self):
        if self._live is None:
            from noesis_agent.runtime.live_media import LiveMediaAgent

            self._live = LiveMediaAgent(
                data_dir=settings.data_dir,
                openai_service=self.openai,
                host_service=self.host,
                memory_service=self.memory,
            )
        return self._live

    def bind_discord_client(self, client) -> None:
        self.output_router.bind_discord_client(client)
        if self._live is not None and hasattr(self._live, "set_discord_client"):
            self._live.set_discord_client(client)

    def is_healthy(self) -> dict[str, object]:
        return {
            "openai_enabled": self.openai.is_enabled(),
            "x_enabled": self.x_client.is_enabled(),
            "store_path": str(self.store.root),
            "runtime_profile": settings.runtime_profile.name,
            "feature_flags": settings.feature_flags.as_dict(),
            "cognition_engine": self.cognition_engine.capability_report(),
            "cognition": [status.model_dump(mode="json") for status in self.cognition.statuses()],
            "live_agent_ready": settings.enable_live_agent,
            "output_channels": [channel.value for channel in self.local_output.capabilities()]
            + [channel.value for channel in self.discord_output.capabilities()],
        }
