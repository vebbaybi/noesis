from __future__ import annotations

import numpy as np


class AudioMixer:
    def mix(self, *tracks: bytes) -> bytes:
        if not tracks:
            return b""
        arrays = [np.frombuffer(t, dtype=np.int16) for t in tracks]
        min_len = min(len(a) for a in arrays)
        stacked = np.vstack([a[:min_len] for a in arrays])
        mixed = np.clip(np.mean(stacked, axis=0), -32768, 32767).astype(np.int16)
        return mixed.tobytes()
