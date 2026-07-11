from __future__ import annotations

from pathlib import Path

from noesis_agent.store.json_store import JsonStore


class MediaStore:
    """Stores metadata about recordings, clips, and published assets."""

    def __init__(self, data_dir: Path) -> None:
        self.store = JsonStore(data_dir / "media")

    def save(self, kind: str, media_id: str, payload: dict) -> None:
        self.store.write(kind, media_id, payload)

    def get(self, kind: str, media_id: str) -> dict | None:
        return self.store.read(kind, media_id)

    def list(self, kind: str) -> list[dict]:
        return self.store.list(kind)
