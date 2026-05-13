from __future__ import annotations

import json
from pathlib import Path
from typing import List

from noesis_agent.models.schemas import TranscriptEvent
from noesis_agent.utils.noesislogger import NoesisLogger


class EpisodicMemory:
    """Persists transcript events per session to disk for recall across shows."""

    def __init__(self, data_dir: Path) -> None:
        self.path = Path(data_dir) / "memory" / "episodes"
        self.path.mkdir(parents=True, exist_ok=True)
        self.logger = NoesisLogger("noesis.memory.episodic").logger

    def append(self, session_id: str, events: list[TranscriptEvent]) -> None:
        file = self.path / f"{session_id}.jsonl"
        with file.open("a", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event.model_dump(mode="json")) + "\n")
        self.logger.debug("Episodic memory persisted", extra={"events": len(events)})

    def load(self, session_id: str) -> list[TranscriptEvent]:
        file = self.path / f"{session_id}.jsonl"
        if not file.exists():
            return []
        events: list[TranscriptEvent] = []
        with file.open("r", encoding="utf-8") as f:
            for line in f:
                events.append(TranscriptEvent.model_validate_json(line))
        return events
