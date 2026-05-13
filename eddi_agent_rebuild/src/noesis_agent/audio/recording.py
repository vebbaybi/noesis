from __future__ import annotations

from pathlib import Path


class AudioRecorder:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save(self, session_id: str, audio_bytes: bytes, ext: str = "wav") -> Path:
        path = self.output_dir / f"{session_id}.{ext}"
        path.write_bytes(audio_bytes)
        return path
