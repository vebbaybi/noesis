from __future__ import annotations

import json

from noesis_agent.clients.openai_client import OpenAIService
from noesis_agent.content import build_local_session_summary, build_summary_thread
from noesis_agent.models.media import SessionSummary
from noesis_agent.services.prompts import build_summary_prompt
from noesis_agent.utils.noesislogger import NoesisLogger


class SummaryService:
    def __init__(self, openai_service: OpenAIService) -> None:
        self.openai_service = openai_service
        self.logger = NoesisLogger("noesis.service.summary").logger

    async def build_summary(self, session_id: str, title: str, transcript_text: str) -> SessionSummary:
        local_summary = build_local_session_summary(session_id=session_id, title=title, transcript_text=transcript_text)

        if self.openai_service.is_enabled():
            prompt = json.dumps({"session_id": session_id, "title": title, "transcript": transcript_text})
            raw = await self.openai_service.generate_text(
                system_prompt=build_summary_prompt(),
                user_prompt=prompt,
                temperature=0.4,
                max_tokens=900,
            )
            try:
                data = json.loads(raw)
                data.setdefault("session_id", session_id)
                data.setdefault("headline", f"{title} recap")
                summary = SessionSummary.model_validate(data)
                if not summary.key_moments:
                    summary = summary.model_copy(update={"key_moments": local_summary.key_moments})
                if not summary.alpha_drops:
                    summary = summary.model_copy(update={"alpha_drops": local_summary.alpha_drops})
                if not summary.funny_moments:
                    summary = summary.model_copy(update={"funny_moments": local_summary.funny_moments})
                if not summary.discord_recap:
                    summary = summary.model_copy(update={"discord_recap": local_summary.discord_recap})
                if not summary.next_episode_ideas:
                    summary = summary.model_copy(update={"next_episode_ideas": local_summary.next_episode_ideas})
                if not summary.x_thread:
                    summary = summary.model_copy(update={"x_thread": build_summary_thread(summary, add_finance_disclaimer=True)})
                return summary
            except (json.JSONDecodeError, ValueError) as exc:
                self.logger.warning(
                    "Summary LLM response could not be parsed; using local summary",
                    exc_info=exc,
                    extra={"session_id": session_id},
                )

        return local_summary
