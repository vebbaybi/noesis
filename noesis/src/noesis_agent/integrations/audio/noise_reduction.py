from __future__ import annotations

import numpy as np


def reduce_noise(audio_bytes: bytes, level: float = 0.8, *, sample_rate: int = 16000) -> bytes:
    """Apply stationary spectral noise reduction to mono 16-bit PCM."""
    if not 0.0 <= level <= 1.0:
        raise ValueError("noise reduction level must be between 0 and 1")
    try:
        import noisereduce as nr
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError('Noise reduction requires the "audio" extra') from exc
    data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    cleaned = nr.reduce_noise(y=data, sr=sample_rate, stationary=True, prop_decrease=level)
    return np.clip(cleaned * 32768.0, -32768, 32767).astype(np.int16).tobytes()
