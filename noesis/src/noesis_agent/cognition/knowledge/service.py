from __future__ import annotations

from noesis_agent.integrations.llm.openai import OpenAIService
from noesis_agent.capabilities.content import build_local_research_brief, render_research_digest
from noesis_agent.domain.entities.knowledge import ResearchBrief
from noesis_agent.cognition.prompts.service import build_research_topic_scan_prompt
from noesis_agent.shared.noesislogger import NoesisLogger


class ResearchService:
    """Lightweight research helper that crafts grounded briefs via OpenAI."""

    def __init__(self, openai_service: OpenAIService) -> None:
        self.openai = openai_service
        self.logger = NoesisLogger("noesis.service.research").logger

    async def quick_brief(self, query: str) -> ResearchBrief:
        if not self.openai.is_enabled():
            return build_local_research_brief(query)

        system_prompt = build_research_topic_scan_prompt(topic=query, depth="brief")
        user_prompt = f"Give the latest on: {query}. Focus on credibility, risk, and brevity."
        text = await self.openai.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.4,
            max_tokens=220,
        )
        return build_local_research_brief(query, raw_text=text, mode="hybrid")

    async def quick_insight(self, query: str) -> str:
        brief = await self.quick_brief(query)
        prefix = "[offline] " if brief.mode == "local" else ""
        return prefix + render_research_digest(brief)


__all__ = ["ResearchService"]
