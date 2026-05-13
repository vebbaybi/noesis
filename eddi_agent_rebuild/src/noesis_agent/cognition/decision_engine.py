from __future__ import annotations

import time
from dataclasses import dataclass

from noesis_agent.cognition.conversation_manager import ConversationManager
from noesis_agent.utils.noesislogger import NoesisLogger


@dataclass
class Decision:
    action: str  # speak | summarize | pivot | invite | wait
    reason: str
    target_speaker: str | None = None
    topic: str | None = None


class DecisionEngine:
    """Policy that decides when and how the agent should intervene."""

    def __init__(
        self,
        conversation: ConversationManager,
        *,
        min_gap_seconds: float = 12.0,
    ) -> None:
        self.conversation = conversation
        self.min_gap_seconds = min_gap_seconds
        self.logger = NoesisLogger("noesis.cognition.decision_engine").logger
        self._last_action_at = 0.0

    def decide(self) -> Decision:
        now = time.time()
        if now - self._last_action_at < self.min_gap_seconds:
            return Decision(action="wait", reason="cooldown")

        # If conversation stalled, summarize
        if not self.conversation.events:
            return Decision(action="wait", reason="no_events_yet")

        recent_text = self.conversation.recent_transcript(limit=6)
        active = list(self.conversation.active_speakers)
        topics = self.conversation.current_topics(limit=3)

        lower_recent = recent_text.lower()

        if len(active) >= 3:
            decision = Decision(action="moderate", reason="too_many_active", target_speaker=active[-1])
        elif "?" in recent_text:
            decision = Decision(action="speak", reason="audience_question", topic=topics[0] if topics else None)
        elif any(marker in lower_recent for marker in ("off topic", "back to", "parking lot")):
            decision = Decision(action="speak", reason="off_topic_recovery", topic=topics[0] if topics else None)
        elif len(self.conversation.events) > 0 and len(self.conversation.events) % 12 == 0:
            decision = Decision(action="summarize", reason="periodic_summary")
        else:
            decision = Decision(action="wait", reason="listening")

        if decision.action != "wait":
            self._last_action_at = now

        self.logger.debug("Decision made", extra=decision.__dict__)
        return decision


__all__ = ["DecisionEngine", "Decision"]
