from __future__ import annotations

from collections import Counter

from noesis_agent.models.media import PostShowArtifacts, SessionSummary
from noesis_agent.models.session import SessionState
from noesis_agent.models.transcript import TranscriptEventType
from noesis_agent.services.summary_service import SummaryService
from noesis_agent.services.transcript_service import TranscriptService
from noesis_agent.utils.noesislogger import NoesisLogger


class PostShowArtifactService:
    """Builds deterministic post-show artifacts from session state."""

    def __init__(self, summary_service: SummaryService, transcript_service: TranscriptService) -> None:
        self.summary_service = summary_service
        self.transcripts = transcript_service
        self.logger = NoesisLogger("noesis.service.post_show").logger

    async def generate(self, state: SessionState) -> PostShowArtifacts:
        transcript_text = self.transcripts.render_text(state.transcript)
        summary = await self.summary_service.build_summary(state.session_id, state.title, transcript_text)
        artifacts = PostShowArtifacts(
            session_id=state.session_id,
            summary=summary,
            highlights=self._highlights(state),
            action_items=self.transcripts.action_items(state.transcript),
            topics=self._topics(state),
            notable_audience_questions=self._questions(state),
            follow_up_ideas=self._follow_up_ideas(state, summary),
        )
        self.logger.info(
            "Post-show artifacts generated",
            extra={"session_id": state.session_id, "highlights": len(artifacts.highlights)},
        )
        return artifacts

    def _highlights(self, state: SessionState) -> list[str]:
        candidates = []
        for event in state.transcript:
            text = event.content.strip()
            lowered = text.lower()
            score = 0
            if event.event_type == TranscriptEventType.QUESTION:
                score += 2
            if any(marker in lowered for marker in ("risk", "signal", "liquidity", "treasury", "action", "follow up")):
                score += 2
            if len(text.split()) >= 8:
                score += 1
            if score:
                candidates.append((score, event.timestamp, text))
        candidates.sort(key=lambda item: (-item[0], item[1]))
        return [text for _score, _timestamp, text in candidates[:6]]

    def _topics(self, state: SessionState) -> list[str]:
        topics = [topic.title for topic in state.session.topic_plan]
        if topics:
            return topics

        words: Counter[str] = Counter()
        stop = {"the", "and", "that", "this", "with", "what", "from", "have", "about", "room"}
        for event in state.transcript:
            for raw in event.content.lower().replace("?", " ").replace(".", " ").split():
                token = raw.strip(",:;!()[]{}")
                if len(token) > 3 and token not in stop:
                    words[token] += 1
        return [word for word, _count in words.most_common(6)]

    def _questions(self, state: SessionState) -> list[str]:
        questions: list[str] = []
        for event in state.transcript:
            if event.event_type == TranscriptEventType.QUESTION or "?" in event.content:
                questions.append(event.content.strip())
        return questions[:8]

    def _follow_up_ideas(self, state: SessionState, summary: SessionSummary) -> list[str]:
        ideas = list(summary.next_episode_ideas)
        for question in self._questions(state):
            cleaned = question.rstrip("?")
            candidate = f"Follow up on: {cleaned}"
            if candidate not in ideas:
                ideas.append(candidate)
        if not ideas:
            topics = self._topics(state)
            if topics:
                ideas.append(f"Revisit {topics[0]} with a sharper evidence check")
            else:
                ideas.append("Open with the strongest unresolved audience question")
        return ideas[:8]


__all__ = ["PostShowArtifactService"]
