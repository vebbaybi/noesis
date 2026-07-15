from __future__ import annotations

import textwrap


class TitleGenerator:
    def generate(self, transcript: str) -> str:
        words = transcript.split()
        return textwrap.shorten(" ".join(words[:20]) or "NOESIS Live Session", width=80, placeholder="…")
