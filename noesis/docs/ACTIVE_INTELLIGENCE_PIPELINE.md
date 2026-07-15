# Active intelligence pipeline

The active Discord mention path is connected to this canonical pipeline and tested locally. It has
not been validated in a live Discord guild.

| Stage | Active owner |
| --- | --- |
| Discord validation and normalization | `integrations.discord.client.NoesisDiscordBot.on_message` and `integrations.mention_normalizers.normalize_discord_message` |
| Tenant and authorization | `integrations.discord.authorization` and `application.mentions.MentionService.handle` |
| Correlation and idempotency | `domain.contracts.intelligence.IntelligenceRequest` and `application.intelligence.IntelligencePipeline.process` |
| Inbound moderation | `capabilities.moderation.pipeline.TwoStageModeration.evaluate` |
| Intervention | `cognition.intervention.InterventionPolicy.decide` |
| Retrieval and context | `application.index_recovery.RecoverableMemoryIndex.retrieve` and `infrastructure.retrieval.SemanticIndex.retrieve` |
| Local-first cognition | `integrations.llm.hybrid.HybridLLMRouter.generate` |
| Structured output and tools | Pydantic discriminated outcomes and `cognition.tools.ToolRegistry.execute` |
| Outbound moderation | `IntelligencePipeline.process` using `ModerationDirection.OUTBOUND` |
| Structured persistence | `RecoverableMemoryIndex.remember` and `JsonSemanticSourceRepository` |
| Semantic indexing | `SemanticIndex.upsert_source` |
| Discord delivery | `application.mentions.MentionDispatcher` and the boundary reply sender |
| Health and telemetry state | `runtime.container.ServiceContainer.is_healthy` |

`tests/test_active_intelligence_pipeline.py` uses actual runtime composition and Discord normalization,
replacing only external model and delivery boundaries with deterministic adapters.
