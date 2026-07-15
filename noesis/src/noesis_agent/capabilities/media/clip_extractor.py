from __future__ import annotations


class ClipExtractor:
    """Simple keyword-based clip marker helper."""

    KEYWORDS = {"alpha", "breaking", "announcement", "recap"}

    def find_markers(self, transcript: str) -> list[int]:
        markers = []
        for idx, line in enumerate(transcript.splitlines()):
            if any(k in line.lower() for k in self.KEYWORDS):
                markers.append(idx)
        return markers
