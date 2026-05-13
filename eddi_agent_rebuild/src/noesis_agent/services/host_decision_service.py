from __future__ import annotations

from noesis_agent.models.live import LiveEventType, LiveSessionEventRequest
from noesis_agent.models.runtime import HostDecision, HostIntent, SessionContext, SpeakerState
from noesis_agent.utils.noesislogger import NoesisLogger


QUESTION_WORDS = ("what", "why", "how", "when", "where", "who", "should", "could", "would", "is", "are", "do", "does")
CONFLICT_MARKERS = ("shut up", "liar", "scam", "rug", "fraud", "attack", "stupid", "idiot")
FOLLOW_UP_MARKERS = ("not sure", "maybe", "unclear", "can you clarify", "what do you mean")
CLOSING_MARKERS = ("wrap up", "close session", "end the show", "final thought", "last question")


class HostDecisionService:
    """Classifies live room events into the next host intent for NOESIS."""

    def __init__(self, *, silence_threshold_seconds: float = 8.0, segment_event_threshold: int = 8) -> None:
        self.silence_threshold_seconds = silence_threshold_seconds
        self.segment_event_threshold = segment_event_threshold
        self.logger = NoesisLogger("noesis.service.host_decision").logger

    def decide(self, context: SessionContext, event: LiveSessionEventRequest) -> HostDecision:
        content = event.content.strip()
        lowered = content.lower()
        active_topic = context.room.active_topic or self._active_topic_from_context(context)
        recent_count = len(context.transcript_tail)

        if event.event_type == LiveEventType.SESSION_ENDED or any(marker in lowered for marker in CLOSING_MARKERS):
            return self._decision(context, HostIntent.CLOSE_SESSION, "session is closing", topic=active_topic)

        if event.event_type == LiveEventType.SESSION_STARTED:
            return self._decision(context, HostIntent.INVITE_SPEAKER, "session started", topic=active_topic, should_respond=True)

        if event.event_type == LiveEventType.SILENCE_DETECTED or context.room.silence_seconds >= self.silence_threshold_seconds:
            return self._decision(
                context,
                HostIntent.RECOVER_SILENCE,
                "room silence exceeded threshold",
                topic=active_topic,
            )

        if event.event_type == LiveEventType.INTERRUPTION or context.room.interruption_active:
            target = event.interrupted_speaker or event.speaker or self._last_active_speaker(context.room.speakers)
            return self._decision(
                context,
                HostIntent.HANDLE_INTERRUPTION,
                "interruption detected",
                target_speaker=target,
                topic=active_topic,
            )

        if event.event_type == LiveEventType.MODERATION_SIGNAL or any(marker in lowered for marker in CONFLICT_MARKERS):
            return self._decision(
                context,
                HostIntent.MODERATE_CONFLICT,
                "moderation or conflict signal detected",
                target_speaker=event.speaker,
                topic=active_topic,
            )

        if "park" in lowered and ("topic" in lowered or "this" in lowered):
            return self._decision(context, HostIntent.PARK_TOPIC, "speaker requested parking topic", topic=active_topic)

        if event.event_type == LiveEventType.TOPIC_CHANGE:
            return self._decision(context, HostIntent.MOVE_TO_NEXT_TOPIC, "topic change requested", topic=event.topic or content)

        if event.event_type == LiveEventType.AUDIENCE_QUESTION or self._looks_like_question(content):
            if any(marker in lowered for marker in FOLLOW_UP_MARKERS) or len(content.split()) <= 4:
                return self._decision(
                    context,
                    HostIntent.ASK_FOLLOW_UP,
                    "question needs clarification",
                    target_speaker=event.speaker,
                    topic=active_topic,
                )
            return self._decision(
                context,
                HostIntent.ANSWER_DIRECTLY,
                "audience question detected",
                target_speaker=event.speaker,
                topic=active_topic,
            )

        if recent_count >= self.segment_event_threshold and recent_count % self.segment_event_threshold == 0:
            return self._decision(context, HostIntent.SUMMARIZE_SEGMENT, "segment reached recap cadence", topic=active_topic)

        if event.event_type == LiveEventType.SPEAKER_JOINED:
            return self._decision(
                context,
                HostIntent.INVITE_SPEAKER,
                "speaker joined",
                target_speaker=event.speaker,
                topic=active_topic,
            )

        if event.event_type in {LiveEventType.SPEAKER_LEFT, LiveEventType.HOST_MESSAGE}:
            return self._decision(context, HostIntent.WAIT, "no host response needed", topic=active_topic, should_respond=False)

        if context.mode in {"solo", "cohost"} and event.event_type == LiveEventType.USER_MESSAGE:
            return self._decision(context, HostIntent.ANSWER_DIRECTLY, "live user message needs response", topic=active_topic)

        return self._decision(context, HostIntent.WAIT, "listening", topic=active_topic, should_respond=False, confidence=0.55)

    def _decision(
        self,
        context: SessionContext,
        intent: HostIntent,
        reason: str,
        *,
        should_respond: bool = True,
        target_speaker: str | None = None,
        topic: str | None = None,
        confidence: float = 0.72,
    ) -> HostDecision:
        decision = HostDecision(
            session_id=context.session_id,
            intent=intent,
            reason=reason,
            should_respond=should_respond,
            target_speaker=target_speaker,
            topic=topic,
            confidence=confidence,
        )
        self.logger.debug("Host decision selected", extra=decision.model_dump(mode="json"))
        return decision

    @staticmethod
    def _looks_like_question(content: str) -> bool:
        stripped = content.strip()
        if not stripped:
            return False
        if "?" in stripped:
            return True
        first = stripped.split(maxsplit=1)[0].lower().strip(".,:")
        return first in QUESTION_WORDS

    @staticmethod
    def _active_topic_from_context(context: SessionContext) -> str | None:
        active = next((topic.title for topic in context.topics if topic.status == "active"), None)
        if active:
            return active
        queued = next((topic.title for topic in context.topics if topic.status == "queued"), None)
        return queued

    @staticmethod
    def _last_active_speaker(speakers: list[SpeakerState]) -> str | None:
        active = [speaker for speaker in speakers if speaker.is_active]
        if not active:
            return None
        return sorted(active, key=lambda speaker: speaker.last_seen_at, reverse=True)[0].display_name


__all__ = ["HostDecisionService"]
