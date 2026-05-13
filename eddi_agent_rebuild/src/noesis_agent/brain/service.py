from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from noesis_agent.brain.adaptive_policy import AdaptiveStylePolicy, PolicyDecision
from noesis_agent.brain.finance_brain import CryptoFinanceReasoner, FinanceInsight
from noesis_agent.brain.humor_engine import HumorEngine, HumorFrame
from noesis_agent.brain.nlp_engine import LocalNLPEngine, TextAnalysis
from noesis_agent.brain.voice_profiles import VoiceProfileManager
from noesis_agent.store.json_store import JsonStore
from noesis_agent.utils.noesislogger import NoesisLogger


@dataclass(frozen=True)
class BrainContext:
    analysis: TextAnalysis
    policy: PolicyDecision
    finance: FinanceInsight
    humor: HumorFrame
    recall_hits: list[str]
    memory_summary: str
    fallback_reply: str
    system_notes: list[str]


class BrainService:
    def __init__(self, *, store: JsonStore, openai_service, memory_service, data_dir: Path) -> None:
        self.store = store
        self.openai = openai_service
        self.memory = memory_service
        self.logger = NoesisLogger("noesis.brain").logger
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
        analysis = self.nlp.analyze(text)
        query_terms = set(analysis.keywords + [token.lower() for token in analysis.finance_entities] + analysis.web3_entities)
        if not query_terms:
            return []

        candidates: list[str] = []

        for topic, facts in getattr(self.memory.semantic, "facts", {}).items():
            topic_terms = set(topic.lower().split("_"))
            if query_terms & topic_terms:
                candidates.extend(fact.content if hasattr(fact, "content") else str(fact) for fact in facts)

        if session_id:
            try:
                events = self.memory.episodic.load(session_id)
            except Exception:
                events = []
            candidates.extend(event.content for event in events)

        scored: list[tuple[float, str]] = []
        for candidate in candidates:
            candidate_analysis = self.nlp.analyze(candidate)
            candidate_terms = set(candidate_analysis.keywords + candidate_analysis.web3_entities)
            overlap = len(query_terms & candidate_terms)
            if overlap <= 0:
                continue
            score = overlap / max(len(query_terms), 1)
            if any(term in candidate.lower() for term in analysis.finance_entities):
                score += 0.15
            scored.append((score, candidate))

        scored.sort(key=lambda item: (-item[0], len(item[1])))

        unique_hits: list[str] = []
        seen = set()
        for _score, candidate in scored:
            key = candidate.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            unique_hits.append(candidate.strip())
            if len(unique_hits) >= limit:
                break
        return unique_hits

    def build_context(
        self,
        *,
        instruction: str,
        latest_context: str,
        transcript_tail: str,
        session_id: str | None = None,
    ) -> BrainContext:
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

        return BrainContext(
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


__all__ = ["BrainContext", "BrainService"]
