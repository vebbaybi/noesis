from __future__ import annotations

import re
from dataclasses import dataclass, field


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
    limitations: tuple[str, ...] = ("heuristic_local_nlp",)


class LocalNLP:
    """Dependency-free interpretation layer; intentionally conservative and measurable."""

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
        intent, confidence = self._intent(lower)
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
                                   confidence < 0.55)

    @staticmethod
    def _intent(text: str) -> tuple[str, float]:
        rules = (
            ("memory_write", ("remember that", "remember this"), 0.95),
            ("memory_forget", ("forget that", "forget this"), 0.95),
            ("platform_state", ("member count", "which channel", "what server", "this thread", "gateway latency"), 0.9),
            ("bug_report", ("bug", "crash", "not working", "broken"), 0.88),
            ("feature_request", ("feature request", "could you add", "add support"), 0.9),
            ("summarize", ("summarize", "recap", "tl;dr"), 0.88),
            ("help", ("what can you do", "help me", "capabilities"), 0.85),
            ("greeting", ("hello", "hey noesis", "gm noesis"), 0.8),
        )
        for intent, markers, confidence in rules:
            if any(marker in text for marker in markers):
                return intent, confidence
        if "?" in text:
            return "question", 0.62
        return "unclear", 0.35


__all__ = ["LocalInterpretation", "LocalNLP"]
