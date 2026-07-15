from __future__ import annotations

import re
from dataclasses import dataclass, field

from noesis_agent.cognition.nlu.intent_model import get_intent_model


@dataclass(frozen=True, slots=True)
class LocalInterpretation:
    language: str
    intent: str
    intent_confidence: float
    dialogue_act: str
    entities: dict[str, list[str]] = field(default_factory=dict)
    topics: list[str] = field(default_factory=list)
    sentiment: str = "neutral"
    emotion: str = "neutral"
    urgency: float = 0.0
    toxicity: float = 0.0
    humor_opportunity: float = 0.0
    requires_clarification: bool = False
    ranked_intents: tuple[tuple[str, float], ...] = ()
    limitations: tuple[str, ...] = ("compact_domain_model", "english_training_corpus")


class LocalNLP:
    """Offline NLU backed by a trained word/character ensemble."""

    _TOPICS = {
        "development": {"code", "repo", "github", "bug", "python", "api", "deploy"},
        "web3": {"crypto", "token", "nft", "dao", "defi", "wallet", "chain", "tvl"},
        "gaming": {"game", "gaming", "player", "guild", "quest"},
        "moderation": {"spam", "harass", "abuse", "ban", "report"},
    }

    def interpret(self, text: str) -> LocalInterpretation:
        normalized = " ".join(text.split())
        lower = normalized.lower()
        words = set(re.findall(r"[a-z0-9']+", lower))
        language = "en" if not re.search(r"[^\x00-\x7f]", normalized) else "und"
        prediction = get_intent_model().predict(normalized)
        intent, confidence = prediction.label, prediction.confidence
        # Explicit speech acts provide stronger evidence than statistical
        # paraphrase inference and are safe confidence anchors.
        if re.search(r"\bfeature request\b", lower):
            intent, confidence = "feature_request", max(confidence, 0.98)
        elif re.search(r"\b(?:bug|broken|crash|exception|not working)\b", lower):
            intent, confidence = "bug_report", max(confidence, 0.9)
        dialogue = "question" if "?" in normalized else "command" if lower.startswith(("please ", "show ", "tell ", "remember ", "forget ")) else "statement"
        topics = [topic for topic, vocabulary in self._TOPICS.items() if words & vocabulary]
        toxic = 0.8 if words & {"idiot", "stupid", "hate", "moron"} else 0.0
        urgent = 0.85 if words & {"urgent", "emergency", "asap", "breach", "hacked"} else 0.0
        serious = urgent > 0 or bool(words & {"loss", "stolen", "breach", "harassment", "emergency", "production"})
        positive = bool(words & {"thanks", "great", "love", "good", "helpful"})
        negative = bool(words & {"broken", "bad", "hate", "loss", "failed"})
        sentiment = "positive" if positive and not negative else "negative" if negative else "neutral"
        emotion = "distress" if serious and negative else "frustration" if negative else "positive" if positive else "neutral"
        entities = {
            "mentions": re.findall(r"@([A-Za-z0-9_]+)", normalized),
            "urls": re.findall(r"https?://[^\s]+", normalized),
            "numbers": re.findall(r"\b\d+(?:\.\d+)?\b", normalized),
        }
        return LocalInterpretation(language, intent, confidence, dialogue, entities, topics,
                                   sentiment, emotion, urgent, toxic, 0.0 if serious else 0.35,
                                   intent == "unclear" or confidence < 0.25, prediction.ranked)


__all__ = ["LocalInterpretation", "LocalNLP"]
