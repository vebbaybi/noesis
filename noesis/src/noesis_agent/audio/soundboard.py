from __future__ import annotations

from pathlib import Path


class Soundboard:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)

    def get_clip(self, name: str) -> bytes | None:
        path = self.base_dir / f"{name}.wav"
        if path.exists():
            return path.read_bytes()
        return None
