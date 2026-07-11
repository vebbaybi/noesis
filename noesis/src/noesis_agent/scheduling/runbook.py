from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Cue:
    label: str
    offset_seconds: int


class Runbook:
    def __init__(self, cues: List[Cue] | None = None) -> None:
        self.cues = cues or []

    def add_cue(self, label: str, offset_seconds: int) -> None:
        self.cues.append(Cue(label, offset_seconds))

    def ordered(self) -> List[Cue]:
        return sorted(self.cues, key=lambda c: c.offset_seconds)
