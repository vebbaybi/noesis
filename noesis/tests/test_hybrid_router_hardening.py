from __future__ import annotations

import asyncio
import importlib.util
from collections.abc import Sequence

import pytest

from noesis_agent.domain.contracts.intelligence import DirectResponse, IntelligenceRequest, RetrievalItem
from noesis_agent.integrations.llm.hybrid import HybridLLMRouter, ProviderConfig


@pytest.fixture(autouse=True)
def _simulate_installed_litellm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise routing policy without requiring the optional provider package."""
    real_find_spec = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name: object() if name == "litellm" else real_find_spec(name),
    )


class _Router(HybridLLMRouter):
    def __init__(self, outcomes: dict[str, object], **kwargs: object) -> None:
        providers = [
            ProviderConfig(name="local", model="local", local=True),
            ProviderConfig(name="remote", model="remote", local=False, api_key="test"),
        ]
        super().__init__(providers, max_attempts=2, cooldown_seconds=60, **kwargs)
        self.outcomes = outcomes
        self.calls: list[str] = []

    async def _call(self, provider: ProviderConfig, request: IntelligenceRequest,
                    context: Sequence[RetrievalItem]):
        self.calls.append(provider.name)
        outcome = self.outcomes[provider.name]
        if isinstance(outcome, BaseException):
            raise outcome
        return DirectResponse(text=str(outcome))


def _request() -> IntelligenceRequest:
    return IntelligenceRequest(event_id="event", tenant_id="tenant", user_id="user",
                               conversation_id="conversation", text="hello")


@pytest.mark.asyncio
async def test_local_success_never_calls_remote() -> None:
    router = _Router({"local": "local ok", "remote": "remote ok"})
    outcome, provider, fallback = await router.generate(_request(), [])
    assert outcome.text == "local ok" and provider == "local" and not fallback
    assert router.calls == ["local"]


@pytest.mark.asyncio
async def test_transient_local_failure_uses_controlled_remote_fallback(monkeypatch) -> None:
    async def no_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    router = _Router({"local": ConnectionError("offline"), "remote": "remote ok"})
    outcome, provider, fallback = await router.generate(_request(), [])
    assert outcome.text == "remote ok" and provider == "remote" and fallback
    assert router.calls == ["local", "remote"]


@pytest.mark.asyncio
async def test_permanent_failure_does_not_fallback() -> None:
    router = _Router({"local": PermissionError("authentication"), "remote": "must not run"})
    with pytest.raises(PermissionError):
        await router.generate(_request(), [])
    assert router.calls == ["local"]


@pytest.mark.asyncio
async def test_malformed_output_degrades_without_executing_remote() -> None:
    router = _Router({"local": ValueError("malformed"), "remote": "must not run"})
    outcome, provider, fallback = await router.generate(_request(), [])
    assert provider == "local:malformed" and fallback
    assert outcome.kind == "direct_response" and router.calls == ["local"]


@pytest.mark.asyncio
async def test_cancellation_stops_fallback() -> None:
    router = _Router({"local": asyncio.CancelledError(), "remote": "must not run"})
    with pytest.raises(asyncio.CancelledError):
        await router.generate(_request(), [])
    assert router.calls == ["local"]


@pytest.mark.asyncio
async def test_circuit_opens_after_repeated_failure_and_closes_after_recovery(monkeypatch) -> None:
    async def no_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    router = _Router({"local": ConnectionError("offline"), "remote": "remote"})
    for _ in range(3):
        await router.generate(_request(), [])
    assert router.health()[0].retry_state == "circuit_open"
    router._circuits["local"].open_until = 0
    router.outcomes["local"] = "recovered"
    outcome, provider, _ = await router.generate(_request(), [])
    assert provider == "local" and outcome.text == "recovered"
    assert router.health()[0].retry_state == "idle"
