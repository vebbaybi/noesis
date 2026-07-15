from __future__ import annotations


class ShowNotesBuilder:
    def build(self, transcript: str) -> str:
        lines = transcript.splitlines()
        bullets = [f"- {line.strip()}" for line in lines[:10] if line.strip()]
        return "\n".join(bullets)
