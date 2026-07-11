from __future__ import annotations


class Chapterizer:
    def chapterize(self, transcript: str, interval_lines: int = 30) -> list[dict]:
        lines = transcript.splitlines()
        chapters = []
        for idx in range(0, len(lines), interval_lines):
            chapters.append({"title": f"Segment {idx//interval_lines +1}", "start_line": idx})
        return chapters
