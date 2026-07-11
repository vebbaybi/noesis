from __future__ import annotations

from pathlib import Path

from noesis_agent.media.show_notes import ShowNotesBuilder
from noesis_agent.media.transcript_formatter import TranscriptFormatter
from noesis_agent.media.title_generator import TitleGenerator
from noesis_agent.media.description_generator import DescriptionGenerator
from noesis_agent.media.chapterizer import Chapterizer


class EpisodeBuilder:
    """Bundles transcripts and metadata into a publishable package."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.notes = ShowNotesBuilder()
        self.formatter = TranscriptFormatter()
        self.titles = TitleGenerator()
        self.describer = DescriptionGenerator()
        self.chapterizer = Chapterizer()

    def build(self, session_id: str, raw_transcript: str) -> dict:
        formatted = self.formatter.format(raw_transcript)
        chapters = self.chapterizer.chapterize(raw_transcript)
        title = self.titles.generate(raw_transcript)
        description = self.describer.generate(raw_transcript)
        notes = self.notes.build(raw_transcript)
        package = {
            "session_id": session_id,
            "title": title,
            "description": description,
            "chapters": chapters,
            "show_notes": notes,
            "transcript": formatted,
        }
        (self.output_dir / f"{session_id}.json").write_text(str(package), encoding="utf-8")
        return package
