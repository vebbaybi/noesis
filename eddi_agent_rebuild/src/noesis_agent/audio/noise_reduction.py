from __future__ import annotations

import numpy as np


def reduce_noise(audio_bytes: bytes, level: float = 0.01) -> bytes:
    data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
    data = np.where(abs(data) < level * 32768, 0, data)
    return data.astype(np.int16).tobytes()
