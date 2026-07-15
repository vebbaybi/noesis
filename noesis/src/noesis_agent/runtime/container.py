from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from noesis_agent.domain.contracts.intelligence import CapabilityHealth

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
        from noesis_agent.application.intelligence.pipeline import IntelligencePipeline
        from noesis_agent.capabilities.moderation.pipeline import DetoxifyModerator, TwoStageModeration
        from noesis_agent.cognition.tools import ToolRegistry
        from noesis_agent.application.components import PersistentComponentService
        from noesis_agent.infrastructure.persistence.component_store import JsonComponentRepository
        from noesis_agent.infrastructure.coordination.idempotency import RedisIdempotencyStore
        from noesis_agent.infrastructure.retrieval.semantic_index import IndexConfig, SemanticIndex
        from noesis_agent.application.index_recovery import RecoverableMemoryIndex
        from noesis_agent.infrastructure.persistence.index_store import JsonSemanticSourceRepository
        from noesis_agent.integrations.llm.hybrid import HybridLLMRouter, ProviderConfig

        self.store = JsonStore(settings.data_dir)
        self.components = PersistentComponentService(JsonComponentRepository(self.store))

        self.openai = OpenAIService()
        self.discord_context_tool = DiscordContextTool()
        catalogue = settings.project_root / "assets" / "users_request.md"
        if not catalogue.is_file():
            catalogue = settings.project_root.parent / "assets" / "users_request.md"
        self.capabilities = CapabilityRegistry(catalogue)
        self.x_client = XClient()
        self.cognition = CognitionProviderRouter.from_settings(self.openai, settings)

        providers = [ProviderConfig(
            name="local", model=settings.local_llm_model, api_base=settings.local_llm_base_url,
            local=True, enabled=settings.local_llm_enabled, timeout_seconds=settings.llm_timeout_seconds,
        )]
        providers.append(ProviderConfig(
            name="openai", model=settings.external_llm_model, api_key=settings.openai_api_key,
            local=False, enabled=settings.external_llm_enabled, timeout_seconds=settings.llm_timeout_seconds,
        ))
        self.hybrid_llm = HybridLLMRouter(
            providers, max_attempts=settings.llm_max_attempts,
            cooldown_seconds=settings.llm_circuit_cooldown_seconds,
            concurrency=settings.llm_concurrency,
        )
        toxicity = DetoxifyModerator(model_name=settings.moderation_model, device=settings.moderation_device,
                                     queue_size=settings.moderation_queue_size,
                                     inference_timeout=settings.moderation_inference_timeout_seconds) \
            if settings.moderation_stage_two_enabled else None
        self.safety = TwoStageModeration(toxicity=toxicity, fail_closed=settings.moderation_fail_closed)
        self.semantic_index = SemanticIndex(IndexConfig(
            url=settings.qdrant_url, collection=settings.qdrant_collection,
            model=settings.embedding_model, dimension=settings.embedding_dimension,
            timeout_seconds=settings.memory_retrieval_timeout_seconds,
        ), enabled=settings.rag_enabled, concurrency=settings.embedding_concurrency)
        self.memory_index = RecoverableMemoryIndex(
            JsonSemanticSourceRepository(self.store), self.semantic_index,
            embedding_model=settings.embedding_model, embedding_dimension=settings.embedding_dimension,
        )
        self.idempotency = RedisIdempotencyStore(settings.redis_url if settings.redis_enabled else "")
        self.tools = ToolRegistry()
        self.intelligence = IntelligencePipeline(
            moderation=self.safety, retrieval=self.memory_index, model=self.hybrid_llm,
            idempotency=self.idempotency, tools=self.tools,
        )

        self.memory = MemoryService(settings.data_dir)
        self.mentions = MentionService(self.openai, noesis_name=settings.noesis_name,
                                       autonomous_memory=self.memory.autonomous if settings.autonomous_memory_enabled else None,
                                       observation_mode=settings.memory_observation_mode,
                                       capability_registry=self.capabilities,
                                       intelligence_pipeline=self.intelligence if settings.intelligence_pipeline_enabled else None)
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
        capability_health = self.capability_health()
        mandatory_failures = [item for item in capability_health if item.mandatory and item.state.value != "ready"]
        return {
            "openai_enabled": self.openai.is_enabled(),
            "x_enabled": self.x_client.is_enabled(),
            "store_path": str(self.store.root),
            "runtime_profile": settings.runtime_profile.name,
            "feature_flags": settings.feature_flags.as_dict(),
            "cognition_engine": self.cognition_engine.capability_report(),
            "cognition": [status.model_dump(mode="json") for status in self.cognition.statuses()],
            "intelligence_stack": {
                "providers": [item.model_dump(mode="json") for item in capability_health if item.name.startswith("llm:")],
                "rag": next(item for item in capability_health if item.name == "rag").model_dump(mode="json"),
                "moderation": next(item for item in capability_health if item.name == "moderation").model_dump(mode="json"),
                "redis": next(item for item in capability_health if item.name == "redis").model_dump(mode="json"),
                "persistent_components": {
                    "state": "ready", "pending": len(self.components.pending()),
                    "validation_level": "locally_tested",
                },
            },
            "liveness": {"state": "alive"},
            "readiness": {
                "state": "not_ready" if mandatory_failures else "ready",
                "mandatory_failures": [item.name for item in mandatory_failures],
            },
            "live_agent_ready": settings.enable_live_agent,
            "output_channels": [channel.value for channel in self.local_output.capabilities()]
            + [channel.value for channel in self.discord_output.capabilities()],
        }

    def capability_health(self) -> list["CapabilityHealth"]:
        from noesis_agent.domain.contracts.intelligence import CapabilityHealth, CapabilityState

        providers = [item.model_copy(update={
            "mandatory": settings.local_llm_required if item.name == "llm:local" else False
        }) for item in self.hybrid_llm.health()]
        rag = self.memory_index.health().model_copy(update={"mandatory": settings.rag_required})
        moderation = self.safety.health().model_copy(update={
            "mandatory": settings.moderation_stage_two_required
        })
        redis = self.idempotency.health().model_copy(update={"mandatory": settings.redis_required})
        discord_state = CapabilityState.DISABLED if not settings.enable_discord else \
            CapabilityState.CREDENTIAL_BLOCKED if not settings.discord_bot_token else CapabilityState.UNVALIDATED
        discord = CapabilityHealth(
            name="discord", state=discord_state, mandatory=False,
            detail="disabled" if discord_state is CapabilityState.DISABLED else
                   "bot token missing" if discord_state is CapabilityState.CREDENTIAL_BLOCKED else
                   "constructed; guild connection not validated",
            validation_level="construction",
        )
        return [*providers, rag, moderation, redis, discord]

    async def start_intelligence(self) -> None:
        await self.semantic_index.initialize()
        if settings.redis_enabled:
            await self.idempotency.validate_service()
        if settings.moderation_warmup:
            await self.safety.warm_up()

    async def close_intelligence(self) -> None:
        await self.semantic_index.close()
        await self.idempotency.close()
        self.safety.close()
