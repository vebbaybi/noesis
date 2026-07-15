from __future__ import annotations

from noesis_agent.runtime.live_media import LiveMediaAgent
from noesis_agent.shared.noesislogger import NoesisLogger


class LiveShowPipeline:
    def __init__(self, live_agent: LiveMediaAgent) -> None:
        self.live = live_agent
        self.logger = NoesisLogger("noesis.pipeline.live_show").logger

    async def start(self, topic: str) -> str:
        session = await self.live.start_autonomous_session(topic=topic)
        self.logger.info("Live show started", extra={"session_id": session.session.session_id})
        return session.session.session_id
