from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

from noesis_agent.capabilities.moderation.pipeline import DetoxifyModerator, LexicalModerator, TwoStageModeration
from noesis_agent.domain.contracts.intelligence import (
    ModerationAction, ModerationDirection,
)
from noesis_agent.infrastructure.config.settings import settings
from noesis_agent.interfaces.api.app import app
from noesis_agent.runtime.container import get_container


class _ScoringDetoxify(DetoxifyModerator):
    def __init__(self, scores: dict[str, float]) -> None:
        super().__init__(thresholds={"toxicity": 0.7, "threat": 0.5})
        self._scores = scores

    def available(self) -> bool:
        return True

    async def predict(self, text: str) -> dict[str, float]:
        return dict(self._scores)

    @property
    def model_version(self) -> str:
        return "test-version"


@pytest.mark.asyncio
async def test_detoxify_score_mapping_and_thresholds() -> None:
    moderation = TwoStageModeration(toxicity=_ScoringDetoxify({"toxicity": 0.8, "threat": 0.2}))
    result = await moderation.evaluate(tenant_id="tenant", text="test",
                                       direction=ModerationDirection.INBOUND)
    by_label = {item.raw_label: item for item in result.score_details}
    assert by_label["toxicity"].category == "toxicity"
    assert by_label["toxicity"].triggered
    assert not by_label["threat"].triggered
    assert result.action is ModerationAction.WARN


@pytest.mark.asyncio
async def test_deep_moderation_failure_policy_open_and_closed(monkeypatch) -> None:
    adapter = _ScoringDetoxify({})

    async def unavailable(text: str) -> dict[str, float]:
        raise RuntimeError("model load failed")

    monkeypatch.setattr(adapter, "predict", unavailable)
    opened = await TwoStageModeration(toxicity=adapter, fail_closed=False).evaluate(
        tenant_id="tenant", text="ordinary", direction=ModerationDirection.INBOUND
    )
    closed = await TwoStageModeration(toxicity=adapter, fail_closed=True).evaluate(
        tenant_id="tenant", text="ordinary", direction=ModerationDirection.INBOUND
    )
    assert opened.action is ModerationAction.ALLOW
    assert closed.action is ModerationAction.DEFER


def test_lexical_allowlist_and_false_positive_boundaries() -> None:
    moderator = LexicalModerator(allowlist={"kill"})
    assert moderator.classify("skillful analysis") == ([], [])
    assert moderator.classify("k.i.l.l") == ([], [])
    active = LexicalModerator()
    assert active.classify("skillful analysis") == ([], [])
    assert active.classify("k i l l")[0] == ["credible_violence"]


@pytest.mark.asyncio
async def test_tenant_specific_lexical_exception() -> None:
    moderation = TwoStageModeration(tenant_lexical={"quoted-material": LexicalModerator(allowlist={"kill"})})
    allowed = await moderation.evaluate(tenant_id="quoted-material", text="quote: k.i.l.l",
                                        direction=ModerationDirection.INBOUND)
    blocked = await moderation.evaluate(tenant_id="ordinary", text="k.i.l.l",
                                        direction=ModerationDirection.INBOUND)
    assert allowed.action is ModerationAction.ALLOW
    assert blocked.action is ModerationAction.BLOCK


def test_detoxify_dependency_absence_is_explicit(monkeypatch) -> None:
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None if name == "detoxify" else object())
    health = DetoxifyModerator().health()
    assert health.state.value == "dependency_unavailable"


@pytest.mark.asyncio
async def test_real_detoxify_cpu_model_when_explicitly_enabled() -> None:
    if os.getenv("NOESIS_RUN_DETOXIFY_MODEL_TEST") != "1":
        pytest.skip("Set NOESIS_RUN_DETOXIFY_MODEL_TEST=1 after caching the optional model weights.")
    adapter = DetoxifyModerator(model_name="original", device="cpu", inference_timeout=120)
    scores = await adapter.predict("Thank you for keeping this discussion constructive.")
    assert {"toxicity", "severe_toxicity", "obscene", "threat", "insult", "identity_attack"} <= set(scores)
    assert adapter.health().validation_level == "real_model"
    adapter.close()


def test_liveness_and_optional_degradation_preserve_readiness(monkeypatch, tmp_path) -> None:
    get_container.cache_clear()
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "local_llm_required", False)
    client = TestClient(app)
    assert client.get("/live").json()["status"] == "alive"
    assert client.get("/ready").status_code == 200


def test_mandatory_unvalidated_provider_blocks_readiness(monkeypatch, tmp_path) -> None:
    get_container.cache_clear()
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "local_llm_required", True)
    response = TestClient(app).get("/ready")
    assert response.status_code == 503
    assert "llm:local" in response.json()["mandatory_failures"]
    get_container.cache_clear()
