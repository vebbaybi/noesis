from __future__ import annotations

from pathlib import Path
from typing import Iterable

from noesis_agent.models.transcript import TranscriptEvent
from noesis_agent.store.json_store import JsonStore


class TranscriptStore:
    def __init__(self, data_dir: Path) -> None:
        self.store = JsonStore(data_dir / "transcripts")

    def append(self, session_id: str, events: Iterable[TranscriptEvent]) -> None:
        for event in events:
            self.store.write(
                "events",
                f"{session_id}:{event.event_id}",
                event.model_dump(mode="json", exclude={"text"}),
            )

    def list(self, session_id: str) -> list[TranscriptEvent]:
        data = self.store.list("events")
        return [TranscriptEvent(**item) for item in data if str(item.get("session_id")) == session_id]
