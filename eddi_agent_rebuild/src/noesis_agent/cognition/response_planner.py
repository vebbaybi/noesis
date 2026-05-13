from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from noesis_agent.cognition.decision_engine import Decision
from noesis_agent.cognition.conversation_manager import ConversationManager
from noesis_agent.models.schemas import HostReplyRequest


@dataclass
class PlannedResponse:
    decision: Decision
    text: str


class HostResponder(Protocol):
    async def generate_reply(
        self,
        payload: HostReplyRequest,
        transcript_tail: str = "",
        session_title: str | None = None,
        session_id: str | None = None,
        room_id: str | None = None,
        current_speaker: str | None = None,
        dry_run: bool = False,
    ):
        ...


class ResponsePlanner:
    """Builds a response text given a decision and conversation state."""

    def __init__(self, host_service: HostResponder, conversation: ConversationManager) -> None:
        self.host_service = host_service
        self.conversation = conversation

    async def plan(self, decision: Decision, session_id: str) -> PlannedResponse | None:
        if decision.action not in {"speak", "summarize", "moderate"}:
            return None

        transcript_tail = self.conversation.recent_transcript(limit=10)
        instruction = ""

        if decision.action == "speak":
            instruction = "Add a concise, high-energy take that moves the topic forward."
        elif decision.action == "summarize":
            instruction = "Give a 2-3 sentence recap and propose the next question."
        elif decision.action == "moderate":
            instruction = f"Politely invite {decision.target_speaker} to wrap up and hand the mic back."

        payload = HostReplyRequest(
            session_id=session_id,
            instruction=instruction,
            latest_transcript_tail=[],
            recent_context_summary=transcript_tail,
            current_speaker=decision.target_speaker,
        )

        reply = await self.host_service.generate_reply(
            payload,
            transcript_tail=transcript_tail,
            session_title="Live session",
            session_id=session_id,
        )

        return PlannedResponse(decision=decision, text=reply.text)


__all__ = ["ResponsePlanner", "PlannedResponse"]
