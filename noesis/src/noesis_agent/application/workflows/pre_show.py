from __future__ import annotations

from noesis_agent.cognition.knowledge.briefing_builder import BriefingBuilder
from noesis_agent.cognition.knowledge.researcher import Researcher
from noesis_agent.shared.noesislogger import NoesisLogger


class PreShowPipeline:
    def __init__(self, researcher: Researcher) -> None:
        self.briefing = BriefingBuilder(researcher)
        self.logger = NoesisLogger("noesis.pipeline.pre_show").logger

    async def run(self, topic: str) -> dict:
        brief = await self.briefing.build(topic)
        self.logger.info("Pre-show briefing ready", extra={"topic": topic})
        return {"topic": topic, "briefing": brief}
