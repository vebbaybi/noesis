from __future__ import annotations

from noesis_agent.models.cognition import CognitionRequest, ProviderCapability, ResponseRoute
from noesis_agent.models.runtime import HostDecision, HostIntent, ResponseMode, SessionContext
from noesis_agent.services.transcript_service import TranscriptService
from noesis_agent.utils.noesislogger import NoesisLogger


class ResponseModeRouter:
    """Maps host decisions into response modes and cognition-provider requests."""

    def __init__(self, transcript_service: TranscriptService) -> None:
        self.transcripts = transcript_service
        self.logger = NoesisLogger("noesis.service.response_mode_router").logger

    def route(self, context: SessionContext, decision: HostDecision) -> ResponseRoute | None:
        if not decision.should_respond or decision.intent == HostIntent.WAIT:
            return None

        mode = self.select_mode(context, decision)
        instruction = self._instruction_for(decision, mode)
        transcript_tail = self.transcripts.render_text(context.transcript_tail[-12:])
        local_fallback = self._local_fallback(context, decision, mode)

        request = CognitionRequest(
            session_id=context.session_id,
            instruction=instruction,
            intent=decision.intent,
            response_mode=mode,
            context=self._context_summary(context, decision),
            transcript_tail=transcript_tail,
            memories=context.memory_refs,
            local_fallback=local_fallback,
            session_context=context,
            required_capabilities=[
                ProviderCapability.HOST_RESPONSE,
                ProviderCapability.MEMORY_AWARE,
            ],
            metadata={
                "response_mode": mode.value,
                "decision_reason": decision.reason,
                "target_speaker": decision.target_speaker,
                "topic": decision.topic,
            },
        )
        route = ResponseRoute(
            decision=decision,
            response_mode=mode,
            cognition_request=request,
            should_generate=True,
            reason=f"{decision.intent.value} -> {mode.value}",
        )
        self.logger.debug("Response route selected", extra={"route": route.reason, "session_id": context.session_id})
        return route

    def select_mode(self, context: SessionContext, decision: HostDecision) -> ResponseMode:
        if decision.intent in {HostIntent.MODERATE, HostIntent.MODERATE_CONFLICT, HostIntent.HANDLE_INTERRUPTION}:
            return ResponseMode.SAFETY_REDIRECT if self._has_safety_signal(context, decision) else ResponseMode.MODERATOR
        if decision.intent in {HostIntent.SUMMARIZE, HostIntent.SUMMARIZE_SEGMENT, HostIntent.END_SEGMENT}:
            return ResponseMode.RECAP
        if decision.intent in {HostIntent.MOVE_TO_NEXT_TOPIC, HostIntent.RECOVER_SILENCE, HostIntent.RECOVER_FROM_SILENCE, HostIntent.PARK_TOPIC}:
            return ResponseMode.TRANSITION
        if decision.intent in {HostIntent.CLOSE_SHOW, HostIntent.CLOSE_SESSION}:
            return ResponseMode.CLOSING
        if context.mode == "guest":
            return ResponseMode.GUEST_REPLY
        if context.mode == "cohost":
            return ResponseMode.COHOST_REPLY
        if decision.intent == HostIntent.INVITE_SPEAKER:
            return ResponseMode.COHOST_REPLY
        if self._needs_deep_answer(context, decision):
            return ResponseMode.DEEP_ANSWER
        return ResponseMode.SHORT_ANSWER

    def _instruction_for(self, decision: HostDecision, mode: ResponseMode) -> str:
        topic = decision.topic or "the current topic"
        target = decision.target_speaker or "the room"
        if mode == ResponseMode.MODERATOR:
            return f"Moderate the room around {topic}. Acknowledge {target}, reduce friction, and restore turn order."
        if mode == ResponseMode.SAFETY_REDIRECT:
            return f"Redirect safely around {topic}. Avoid escalation, refuse unsafe claims, and move the room back to useful ground."
        if mode == ResponseMode.RECAP:
            return f"Recap the current segment on {topic} in 2-3 sentences and tee up the next useful question."
        if mode == ResponseMode.TRANSITION:
            return f"Transition from the current thread into {topic}. Keep momentum and make the next question clear."
        if mode == ResponseMode.CLOSING:
            return "Close the session with a concise summary, thanks, and clear follow-up direction."
        if mode == ResponseMode.GUEST_REPLY:
            return f"Reply as a guest on {topic}: specific, useful, and respectful of the host."
        if mode == ResponseMode.COHOST_REPLY:
            return f"Reply as a co-host on {topic}: support the host, add signal, and leave space."
        if mode == ResponseMode.DEEP_ANSWER:
            return f"Give a deeper answer on {topic}; include tradeoffs, risk, and what evidence would change the view."
        return f"Answer directly on {topic}. Keep it short, clear, and live-room ready."

    def _context_summary(self, context: SessionContext, decision: HostDecision) -> str:
        speakers = ", ".join(s.display_name for s in context.room.speakers if s.is_active) or "none"
        topic_status = ", ".join(f"{topic.title}:{topic.status}" for topic in context.topics[:8]) or "no topic queue"
        return (
            f"Session: {context.title}\n"
            f"Mode: {context.mode}\n"
            f"Room: {context.room.status}; energy={context.room.energy_level}; active_speakers={speakers}\n"
            f"Topics: {topic_status}\n"
            f"Decision: {decision.intent.value}; reason={decision.reason}"
        )

    def _local_fallback(self, context: SessionContext, decision: HostDecision, mode: ResponseMode) -> str:
        topic = decision.topic or context.room.active_topic or "this thread"
        if mode == ResponseMode.RECAP:
            return f"Quick recap: the useful thread is {topic}. The room should keep the strongest signal, name the risk, and move to the next question."
        if mode == ResponseMode.TRANSITION:
            return f"Let's move from {topic} into the next useful angle. The clean question is what evidence changes the read."
        if mode in {ResponseMode.MODERATOR, ResponseMode.SAFETY_REDIRECT}:
            return "Let's keep it clean and useful: one speaker at a time, challenge claims with evidence, and bring it back to the topic."
        if mode == ResponseMode.CLOSING:
            return "Strong session. The takeaway is to separate signal from hype, keep the risk visible, and carry the best follow-ups into the next room."
        return f"On {topic}: answer the actual question first, frame the risk, and keep the room moving."

    @staticmethod
    def _needs_deep_answer(context: SessionContext, decision: HostDecision) -> bool:
        recent_text = " ".join(event.content for event in context.transcript_tail[-3:]).lower()
        return any(marker in recent_text for marker in ("why", "how", "explain", "break down", "risk", "tradeoff"))

    @staticmethod
    def _has_safety_signal(context: SessionContext, decision: HostDecision) -> bool:
        text = " ".join(event.content for event in context.transcript_tail[-5:]).lower()
        reason = decision.reason.lower()
        return any(marker in f"{text} {reason}" for marker in ("abuse", "harass", "threat", "dox", "scam", "fraud"))


__all__ = ["ResponseModeRouter"]
