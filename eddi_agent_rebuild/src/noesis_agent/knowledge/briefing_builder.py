from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from noesis_agent.knowledge.researcher import Researcher
from noesis_agent.utils.noesislogger import NoesisLogger


@dataclass
class Briefing:
    topic: str
    bullets: list[str]
    sources: list[dict[str, str]]


class BriefingBuilder:
    def __init__(self, researcher: Researcher) -> None:
        self.researcher = researcher
        self.logger = NoesisLogger("noesis.knowledge.briefing").logger

    async def build(self, topic: str) -> Briefing:
        findings = await self.researcher.search(topic, max_results=8)
        bullets = [f"{i+1}. {item['title']}" for i, item in enumerate(findings) if item.get("title")]
        return Briefing(topic=topic, bullets=bullets, sources=findings)
