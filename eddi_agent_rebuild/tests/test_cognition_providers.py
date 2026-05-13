from __future__ import annotations

import asyncio

import pytest

from noesis_agent.cognition.providers import CognitionProviderRouter, FutureELKAProvider, LocalLLMProvider
from noesis_agent.models.cognition import CognitionRequest
from noesis_agent.utils.errors import ConfigurationError


class DisabledOpenAI:
    def is_enabled(self) -> bool:
        return False


def test_local_provider_returns_explicit_local_fallback() -> None:
    provider = LocalLLMProvider(DisabledOpenAI())
    request = CognitionRequest(
        session_id="session-1",
        instruction="Answer the room.",
        context="guest: What is the risk?",
        local_fallback="[OpenAI unavailable] Risk first, upside second.",
    )

    response = asyncio.run(provider.generate(request))

    assert response.used_fallback is True
    assert response.provider_name == "local-fallback"
    assert "OpenAI unavailable" in response.text


def test_elka_provider_is_disabled_until_configured() -> None:
    provider = FutureELKAProvider(base_url="", enabled=False)
    status = provider.status()

    assert status.available is False
    with pytest.raises(ConfigurationError):
        asyncio.run(
            provider.generate(
                CognitionRequest(session_id="session-1", instruction="Use ELKA if available.")
            )
        )


def test_router_auto_falls_back_to_local_when_elka_disabled() -> None:
    router = CognitionProviderRouter(
        local_provider=LocalLLMProvider(DisabledOpenAI()),
        elka_provider=FutureELKAProvider(base_url="", enabled=False),
        preferred_provider="auto",
    )

    response = asyncio.run(
        router.generate(
            CognitionRequest(
                session_id="session-1",
                instruction="Answer locally.",
                context="The room is asking for a fast take.",
            )
        )
    )

    assert response.provider_name == "local-fallback"
    assert response.used_fallback is True
