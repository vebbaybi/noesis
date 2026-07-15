from __future__ import annotations

from collections.abc import Sequence

import pytest

from noesis_agent.domain.contracts.intelligence import (
    CapabilityHealth, CapabilityState, DirectResponse, IntelligenceRequest, RetrievalItem,
)
from noesis_agent.infrastructure.config.settings import settings
from noesis_agent.integrations.mention_normalizers import normalize_discord_message
from noesis_agent.runtime.container import ServiceContainer


class _DeterministicModel:
    def __init__(self) -> None:
        self.requests: list[IntelligenceRequest] = []

    async def generate(self, request: IntelligenceRequest,
                       context: Sequence[RetrievalItem]):
        self.requests.append(request)
        return DirectResponse(text="Canonical pipeline response."), "deterministic-test-adapter", False

    def health(self) -> list[CapabilityHealth]:
        return [CapabilityHealth(name="llm:test", state=CapabilityState.READY,
                                 validation_level="deterministic_test_adapter")]


@pytest.mark.asyncio
async def test_normalized_discord_mention_reaches_runtime_composed_pipeline(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "enable_live_mention_send", False)
    monkeypatch.setattr(settings, "enable_discord_mention_send", False)
    container = ServiceContainer()
    model = _DeterministicModel()
    container.intelligence._model = model
    event = normalize_discord_message({
        "id": "discord-e2e-1", "content": "@Noesis explain recovery guarantees",
        "author": {"id": "user-1", "name": "Tester"},
        "channel": {"id": "channel-1", "name": "general"},
        "guild": {"id": "guild-1"}, "mentions": [{"id": "bot-1"}],
    }, bot_user_id="bot-1")
    event.metadata["guild_id"] = "guild-1"
    event.metadata["authorization_reason"] = "allowed"
    result = await container.mention_dispatcher.dispatch(event, live=True)
    assert model.requests and model.requests[0].tenant_id == "guild-1"
    assert result.response_text == "Canonical pipeline response."
    assert result.send_mode == "disabled"
    stored = container.store.list("semantic_sources")
    assert stored and stored[0]["tenant_id"] == "guild-1"
