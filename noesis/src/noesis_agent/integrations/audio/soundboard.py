from __future__ import annotations

from pathlib import Path
import re


class Soundboard:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)

    def get_clip(self, name: str) -> bytes | None:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", name).strip("._")
        if not safe_name:
            return None
        path = self.base_dir / f"{safe_name}.wav"
        if path.exists():
            return path.read_bytes()
        return None
