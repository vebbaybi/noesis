from __future__ import annotations

from functools import lru_cache

from noesis_agent.config.settings import settings


@lru_cache(maxsize=1)
def get_container() -> "ServiceContainer":
    return ServiceContainer()


class ServiceContainer:
    def __init__(self) -> None:
        from noesis_agent.brain.service import BrainService
        from noesis_agent.clients.openai_client import OpenAIService
        from noesis_agent.clients.x_client import XClient
        from noesis_agent.cognition.providers import CognitionProviderRouter
        from noesis_agent.services.host_service import HostService
        from noesis_agent.services.host_runtime_service import HostRuntimeService
        from noesis_agent.services.host_decision_service import HostDecisionService
        from noesis_agent.services.live_session_service import LiveSessionService
        from noesis_agent.services.memory_service import MemoryService
        from noesis_agent.services.mention_service import MentionService
        from noesis_agent.services.output_adapters import DiscordOutputAdapter, LocalTextOutputAdapter
        from noesis_agent.services.output_router import OutputRouter
        from noesis_agent.services.post_show_service import PostShowArtifactService
        from noesis_agent.services.planner_service import PlannerService
        from noesis_agent.services.publisher_service import PublisherService
        from noesis_agent.services.research_service import ResearchService
        from noesis_agent.services.response_mode_router import ResponseModeRouter
        from noesis_agent.services.session_service import SessionService
        from noesis_agent.services.social_service import SocialService
        from noesis_agent.services.summary_service import SummaryService
        from noesis_agent.services.topic_planning_service import TopicPlanningService
        from noesis_agent.services.transcript_service import TranscriptService
        from noesis_agent.store.json_store import JsonStore

        self.store = JsonStore(settings.data_dir)

        self.openai = OpenAIService()
        self.mentions = MentionService(self.openai, noesis_name=settings.noesis_name)
        self.x_client = XClient()
        self.cognition = CognitionProviderRouter.from_settings(self.openai, settings)

        self.memory = MemoryService(settings.data_dir)
        self.brain = BrainService(
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
            brain_service=self.brain,
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
            from noesis_agent.services.platform_service import PlatformService

            self._platform = PlatformService(openai=self.openai)
        return self._platform

    @property
    def analytics(self):
        if self._analytics is None:
            from noesis_agent.services.analytics_service import AnalyticsService

            self._analytics = AnalyticsService()
        return self._analytics

    @property
    def recording(self):
        if self._recording is None:
            from noesis_agent.services.recording_service import RecordingService

            self._recording = RecordingService(settings.data_dir / "recordings")
        return self._recording

    @property
    def voice(self):
        if self._voice is None:
            from noesis_agent.services.voice_service import VoiceService

            self._voice = VoiceService(self.openai, self.brain.voice_profiles)
        return self._voice

    @property
    def moderation(self):
        if self._moderation is None:
            from noesis_agent.services.moderation_service import ModerationService

            self._moderation = ModerationService()
        return self._moderation

    @property
    def live(self):
        if self._live is None:
            from noesis_agent.services.live_service import LiveMediaAgent

            self._live = LiveMediaAgent(
                data_dir=settings.data_dir,
                openai_service=self.openai,
                host_service=self.host,
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
            "brain": self.brain.capability_report(),
            "cognition": [status.model_dump(mode="json") for status in self.cognition.statuses()],
            "live_agent_ready": settings.enable_live_agent,
            "output_channels": [channel.value for channel in self.local_output.capabilities()]
            + [channel.value for channel in self.discord_output.capabilities()],
        }
