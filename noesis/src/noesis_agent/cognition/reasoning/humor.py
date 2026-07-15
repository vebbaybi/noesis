from __future__ import annotations

from dataclasses import dataclass

from noesis_agent.cognition.reasoning.finance import FinanceInsight
from noesis_agent.cognition.nlu.analysis import TextAnalysis


@dataclass(frozen=True)
class HumorFrame:
    enabled: bool
    style: str
    boundary: str
    hooks: list[str]
    summary: str


class HumorEngine:
    def plan(self, analysis: TextAnalysis, finance: FinanceInsight, selected_style: str) -> HumorFrame:
        style = "dry"
        enabled = analysis.humor_score >= 0.2 or selected_style == "humorous"
        boundary = "Keep the joke light, never punch down, and never make losses sound trivial."

        if selected_style == "humorous" and finance.risk_level == "low":
            style = "playful"
        elif finance.risk_level == "high":
            style = "dry"
        elif analysis.humor_score >= 0.45:
            style = "satirical"

        hooks: list[str] = []
        subject = analysis.keywords[0] if analysis.keywords else "the market"

        if enabled:
            if finance.active:
                hooks.append(f"Keep one clean line that cuts through cope around {subject}.")
                hooks.append("Use wit to separate signal from noise, not to flex.")
            else:
                hooks.append(f"Use a sharp aside about {subject} without derailing the point.")

        summary = f"humor_enabled={enabled}; style={style}; boundary={boundary}"
        return HumorFrame(enabled=enabled, style=style, boundary=boundary, hooks=hooks, summary=summary)


__all__ = ["HumorEngine", "HumorFrame"]
