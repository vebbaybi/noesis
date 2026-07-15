from __future__ import annotations

from pathlib import Path
import re


class AudioRecorder:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save(self, session_id: str, audio_bytes: bytes, ext: str = "wav",
             *, sample_rate: int = 16000) -> Path:
        safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id).strip("._")
        if not safe_id:
            raise ValueError("session_id must contain a filename-safe character")
        if ext.casefold() != "wav":
            raise ValueError("raw PCM recording currently supports WAV output only")
        path = self.output_dir / f"{safe_id}.wav"
        try:
            import soundfile as sf
            import numpy as np
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise RuntimeError('Audio recording requires the "audio" extra') from exc
        samples = np.frombuffer(audio_bytes, dtype=np.int16)
        sf.write(path, samples, sample_rate, subtype="PCM_16", format="WAV")
        return path
