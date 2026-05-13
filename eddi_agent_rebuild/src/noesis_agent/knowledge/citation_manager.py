from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class Citation:
    text: str
    url: str | None = None
    score: float | None = None


class CitationManager:
    def attach(self, text: str, sources: Iterable[dict]) -> list[Citation]:
        citations = []
        for src in sources:
            citations.append(
                Citation(
                    text=text,
                    url=src.get("url"),
                    score=float(src.get("score", 0.0)) if "score" in src else None,
                )
            )
        return citations
