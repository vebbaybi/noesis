from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from noesis_agent.brain.nlp_engine import TextAnalysis
from noesis_agent.store.json_store import JsonStore


DEFAULT_ACTIONS = ("balanced", "analytical", "educational", "humorous", "skeptical")
DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
    "balanced": {
        "bias": 0.25,
        "finance_score": 0.45,
        "humor_score": 0.25,
        "risk_pressure": -0.15,
        "question_pressure": 0.35,
        "complexity": 0.25,
    },
    "analytical": {
        "bias": 0.15,
        "finance_score": 1.05,
        "humor_score": -0.35,
        "risk_pressure": 0.45,
        "question_pressure": 0.35,
        "complexity": 0.65,
    },
    "educational": {
        "bias": 0.1,
        "finance_score": 0.55,
        "humor_score": -0.1,
        "risk_pressure": 0.2,
        "question_pressure": 0.8,
        "complexity": 0.55,
    },
    "humorous": {
        "bias": 0.05,
        "finance_score": 0.1,
        "humor_score": 1.15,
        "risk_pressure": -0.65,
        "question_pressure": 0.1,
        "complexity": -0.05,
    },
    "skeptical": {
        "bias": 0.1,
        "finance_score": 0.75,
        "humor_score": -0.2,
        "risk_pressure": 1.05,
        "question_pressure": 0.15,
        "complexity": 0.35,
    },
}


@dataclass(frozen=True)
class PolicyDecision:
    style: str
    score: float
    feature_snapshot: dict[str, float]
    rationale: list[str]


class AdaptiveStylePolicy:
    def __init__(
        self,
        store: JsonStore,
        *,
        namespace: str = "brain_policy",
        key: str = "adaptive_style",
        learning_rate: float = 0.08,
    ) -> None:
        self.store = store
        self.namespace = namespace
        self.key = key
        self.learning_rate = learning_rate
        persisted = self.store.read(namespace, key) or {}
        self.weights = self._load_weights(persisted.get("weights"))
        self.usage = {action: int(count) for action, count in (persisted.get("usage") or {}).items()}

    def _load_weights(self, payload: Any) -> dict[str, dict[str, float]]:
        if not isinstance(payload, dict):
            return {action: dict(weights) for action, weights in DEFAULT_WEIGHTS.items()}

        weights: dict[str, dict[str, float]] = {action: dict(DEFAULT_WEIGHTS[action]) for action in DEFAULT_ACTIONS}
        for action, feature_map in payload.items():
            if action not in weights or not isinstance(feature_map, dict):
                continue
            for feature, value in feature_map.items():
                try:
                    weights[action][feature] = float(value)
                except (TypeError, ValueError):
                    continue
        return weights

    def _persist(self) -> None:
        self.store.write(
            self.namespace,
            self.key,
            {
                "weights": self.weights,
                "usage": self.usage,
            },
        )

    def _feature_vector(self, analysis: TextAnalysis) -> dict[str, float]:
        return {
            "finance_score": float(analysis.finance_score),
            "humor_score": float(analysis.humor_score),
            "risk_pressure": min(1.0, len(analysis.risk_flags) * 0.35),
            "question_pressure": min(1.0, analysis.question_count * 0.5),
            "complexity": float(analysis.complexity_score),
        }

    def select_style(self, analysis: TextAnalysis) -> PolicyDecision:
        features = self._feature_vector(analysis)
        scored: list[tuple[str, float]] = []
        for action, weights in self.weights.items():
            score = weights.get("bias", 0.0)
            for feature, value in features.items():
                score += weights.get(feature, 0.0) * value
            scored.append((action, round(score, 4)))

        style, score = max(scored, key=lambda item: item[1])
        self.usage[style] = self.usage.get(style, 0) + 1
        self._persist()

        rationale: list[str] = []
        if features["finance_score"] >= 0.35:
            rationale.append("finance heavy context")
        if features["risk_pressure"] >= 0.35:
            rationale.append("heightened risk language")
        if features["question_pressure"] >= 0.5:
            rationale.append("needs direct answers")
        if features["humor_score"] >= 0.4:
            rationale.append("humor-friendly room energy")
        if not rationale:
            rationale.append("default balanced delivery")

        return PolicyDecision(style=style, score=score, feature_snapshot=features, rationale=rationale)

    def record_feedback(self, style: str, reward: float, feature_snapshot: dict[str, float]) -> None:
        if style not in self.weights:
            return

        bounded_reward = max(-1.0, min(1.0, float(reward)))
        action_weights = self.weights[style]
        action_weights["bias"] = action_weights.get("bias", 0.0) + (self.learning_rate * bounded_reward * 0.15)

        for feature, value in feature_snapshot.items():
            action_weights[feature] = action_weights.get(feature, 0.0) + (
                self.learning_rate * bounded_reward * float(value)
            )

        self._persist()


__all__ = ["AdaptiveStylePolicy", "PolicyDecision"]
