from __future__ import annotations

import asyncio
import importlib.util
import re
import unicodedata
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol, cast

from noesis_agent.domain.contracts.intelligence import (
    CapabilityHealth, CapabilityState, FailureCategory, ModerationAction,
    ModerationDecision, ModerationDirection,
)

_ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
_SEPARATORS = re.compile(r"(?<=\w)[._-]+(?=\w)")
_REPEATED = re.compile(r"(.)\1{2,}")
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})


class LexicalModerator:
    """Deterministic Unicode/evasion normalization; original content is never mutated."""

    def __init__(self, terms: Mapping[str, set[str]] | None = None) -> None:
        self._terms = terms or {
            "credible_violence": {"kill", "bomb", "shoot"},
            "self_harm": {"suicide", "selfharm"},
            "abuse": {"slur"},
        }

    @staticmethod
    def normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text).casefold()
        normalized = _ZERO_WIDTH.sub("", normalized).translate(_LEET)
        previous = ""
        while normalized != previous:
            previous, normalized = normalized, _SEPARATORS.sub("", normalized)
        return _REPEATED.sub(r"\1\1", normalized)

    def classify(self, text: str) -> tuple[list[str], list[str]]:
        normalized = self.normalize(text)
        categories: list[str] = []
        evidence: list[str] = []
        for category, terms in self._terms.items():
            matched = sorted(term for term in terms if re.search(
                rf"(?<!\w){self._evasion_pattern(term)}(?!\w)", normalized
            ))
            if matched:
                categories.append(category)
                evidence.extend(f"{category}:{term[:2]}***" for term in matched)
        return categories, evidence

    @staticmethod
    def _evasion_pattern(term: str) -> str:
        return r"[\W_]*".join(re.escape(char) for char in term)


class _DetoxifyModel(Protocol):
    def predict(self, text: str) -> Mapping[str, object]: ...


class DetoxifyModerator:
    """Lazy bounded adapter around Detoxify's synchronous predict API."""

    def __init__(self, *, model_name: str = "original", device: str = "cpu",
                 thresholds: Mapping[str, float] | None = None, queue_size: int = 16) -> None:
        self._model_name = model_name
        self._device = device
        self._thresholds = dict(thresholds or {"toxicity": 0.75, "severe_toxicity": 0.6,
                                               "identity_attack": 0.7, "insult": 0.75, "threat": 0.6})
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="noesis-detoxify")
        self._slots = asyncio.Semaphore(queue_size)
        self._model: _DetoxifyModel | None = None
        self._failure = ""

    def available(self) -> bool:
        return importlib.util.find_spec("detoxify") is not None

    async def predict(self, text: str) -> dict[str, float]:
        if not self.available():
            raise ModuleNotFoundError("Install noesis-agent[moderation] to enable Detoxify.")
        async with self._slots:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self._executor, self._predict_sync, text)

    def _predict_sync(self, text: str) -> dict[str, float]:
        if self._model is None:
            from detoxify import Detoxify
            self._model = cast(_DetoxifyModel, Detoxify(self._model_name, device=self._device))
        raw = self._model.predict(text)
        return {str(key): float(str(value)) for key, value in raw.items()}

    @property
    def thresholds(self) -> dict[str, float]:
        return dict(self._thresholds)

    def health(self) -> CapabilityHealth:
        if not self.available():
            return CapabilityHealth(name="detoxify", state=CapabilityState.UNAVAILABLE,
                                    detail="optional dependency not installed")
        return CapabilityHealth(name="detoxify", state=CapabilityState.READY if self._model else CapabilityState.LOADING,
                                detail=self._failure or "lazy model load")

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


class TwoStageModeration:
    def __init__(self, lexical: LexicalModerator | None = None, toxicity: DetoxifyModerator | None = None,
                 *, fail_closed: bool = False) -> None:
        self._lexical = lexical or LexicalModerator()
        self._toxicity = toxicity
        self._fail_closed = fail_closed

    async def evaluate(self, *, tenant_id: str, text: str,
                       direction: ModerationDirection) -> ModerationDecision:
        lexical, evidence = self._lexical.classify(text)
        scores: dict[str, float] = {}
        failure: FailureCategory | None = None
        if self._toxicity is not None:
            try:
                scores = await self._toxicity.predict(text)
            except ModuleNotFoundError:
                failure = FailureCategory.CONNECTION
        thresholds = self._toxicity.thresholds if self._toxicity else {}
        triggered = sorted({*lexical, *(key for key, score in scores.items()
                                        if score >= thresholds.get(key, 1.01))})
        action = ModerationAction.BLOCK if {"credible_violence", "threat"} & set(triggered) else \
            ModerationAction.WARN if triggered else ModerationAction.ALLOW
        if failure is not None and self._fail_closed:
            action = ModerationAction.DEFER
        return ModerationDecision(
            tenant_id=tenant_id, direction=direction, action=action,
            lexical_categories=lexical, toxicity_scores=scores, triggered_categories=triggered,
            thresholds=thresholds, model_version="detoxify:original" if scores else "unavailable",
            evidence=evidence, failure=failure, review_eligible=bool(triggered),
        )

    def health(self) -> CapabilityHealth:
        if self._toxicity is None:
            return CapabilityHealth(name="moderation", state=CapabilityState.DEGRADED,
                                    detail="lexical stage ready; toxicity stage disabled")
        return self._toxicity.health().model_copy(update={"name": "moderation"})
