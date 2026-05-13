from __future__ import annotations

import textwrap


class DescriptionGenerator:
    def generate(self, transcript: str) -> str:
        return textwrap.shorten(transcript.replace("\n", " "), width=320, placeholder="…")
