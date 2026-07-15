from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from noesis_agent.cognition.policies.style import AdaptiveStylePolicy, PolicyDecision
from noesis_agent.cognition.reasoning.finance import CryptoFinanceReasoner, FinanceInsight
from noesis_agent.cognition.reasoning.humor import HumorEngine, HumorFrame
from noesis_agent.cognition.nlu.analysis import LocalNLPEngine, TextAnalysis
from noesis_agent.integrations.audio.voice_profiles import VoiceProfileManager
from noesis_agent.infrastructure.persistence.json_store import JsonStore
from noesis_agent.shared.noesislogger import NoesisLogger


@dataclass(frozen=True)
class CognitionContext:
    analysis: TextAnalysis
    policy: PolicyDecision
    finance: FinanceInsight
    humor: HumorFrame
    recall_hits: list[str]
    memory_summary: str
    fallback_reply: str
    system_notes: list[str]


class CognitionEngine:
    def __init__(self, *, store: JsonStore, openai_service, memory_service, data_dir: Path) -> None:
        self.store = store
        self.openai = openai_service
        self.memory = memory_service
        self.logger = NoesisLogger("noesis.cognition.engine").logger
        self.nlp = LocalNLPEngine()
        self.policy = AdaptiveStylePolicy(store)
        self.finance = CryptoFinanceReasoner()
        self.humor = HumorEngine()
        self.voice_profiles = VoiceProfileManager(store, data_dir)

    def capability_report(self) -> dict[str, object]:
        return {
            "ml": {
                "local": ["adaptive style policy", "hybrid retrieval scoring", "financial reasoning heuristics"],
                "api": ["OpenAI generation when enabled"],
            },
            "dl": {
                "local": ["Whisper and diarization pipelines elsewhere in the repo"],
                "api": ["OpenAI LLM and TTS"],
            },
            "rl": {
                "local": ["reward-updated response style policy"],
                "api": [],
            },
            "nlp": {
                "local": ["intent detection", "keyword extraction", "risk detection", "finance/web3 entity tagging"],
                "api": ["prompt-grounded generation when enabled"],
            },
        }

    def recall(self, text: str, session_id: str | None = None, limit: int = 6) -> list[str]:
        return self.memory.recall(text, session_id=session_id, limit=limit)

    def build_context(
        self,
        *,
        instruction: str,
        latest_context: str,
        transcript_tail: str,
        session_id: str | None = None,
    ) -> CognitionContext:
        combined = "\n".join(part for part in [instruction, latest_context, transcript_tail] if part.strip())
        analysis = self.nlp.analyze(combined)
        policy = self.policy.select_style(analysis)
        finance = self.finance.analyze(analysis)
        humor = self.humor.plan(analysis, finance, policy.style)
        recall_hits = self.recall(combined, session_id=session_id)
        memory_summary = " | ".join(recall_hits[:3]) if recall_hits else "No high-confidence memory hits."

        system_notes = [
            "Operate as NOESIS: sharp, fast, funny when useful, never vague.",
            f"Local NLP summary: {analysis.prompt_summary()}",
            f"Adaptive policy: style={policy.style}; rationale={', '.join(policy.rationale)}",
            f"Finance reasoning: {finance.prompt_summary}",
            f"Humor: {humor.summary}",
        ]
        if recall_hits:
            system_notes.append(f"Relevant local memory: {memory_summary}")

        fallback_reply = self._build_local_fallback_reply(
            analysis=analysis,
            policy=policy,
            finance=finance,
            humor=humor,
            recall_hits=recall_hits,
        )

        return CognitionContext(
            analysis=analysis,
            policy=policy,
            finance=finance,
            humor=humor,
            recall_hits=recall_hits,
            memory_summary=memory_summary,
            fallback_reply=fallback_reply,
            system_notes=system_notes,
        )

    def _build_local_fallback_reply(
        self,
        *,
        analysis: TextAnalysis,
        policy: PolicyDecision,
        finance: FinanceInsight,
        humor: HumorFrame,
        recall_hits: list[str],
    ) -> str:
        openings = {
            "balanced": "Here is the quick read:",
            "analytical": "Here is the clean read:",
            "educational": "Quick breakdown:",
            "humorous": "Here is the non-delusional version:",
            "skeptical": "Here is the part worth questioning:",
        }
        segments = [openings.get(policy.style, "Here is the quick read:")]

        if finance.active:
            segments.append(finance.guidance[0])
            if finance.risk_level != "low":
                segments.append("Call out the downside, the timeframe, and what would invalidate the thesis.")
        elif "question_answering" in analysis.intents:
            segments.append("Answer the actual question first, then add one concrete next check.")
        else:
            segments.append("Keep the room moving with one concrete point and one clean pivot.")

        if recall_hits:
            reference = recall_hits[0]
            if len(reference) > 140:
                reference = reference[:137].rstrip() + "..."
            segments.append(f"This also lines up with earlier context: {reference}")

        if humor.enabled and humor.hooks:
            segments.append(humor.hooks[0])

        return " ".join(segment.strip() for segment in segments if segment.strip())

    def record_feedback(self, style: str, reward: float, text: str) -> None:
        analysis = self.nlp.analyze(text)
        self.policy.record_feedback(style=style, reward=reward, feature_snapshot=self.policy._feature_vector(analysis))


__all__ = ["CognitionContext", "CognitionEngine"]
