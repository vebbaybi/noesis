from __future__ import annotations

from pathlib import Path

from noesis_agent.capabilities.media.episode_builder import EpisodeBuilder
from noesis_agent.shared.noesislogger import NoesisLogger


class PostShowPipeline:
    def __init__(self, output_dir: Path) -> None:
        self.builder = EpisodeBuilder(output_dir)
        self.logger = NoesisLogger("noesis.pipeline.post_show").logger

    def run(self, session_id: str, raw_transcript: str) -> dict:
        package = self.builder.build(session_id, raw_transcript)
        self.logger.info("Post show package built", extra={"session_id": session_id})
        return package
