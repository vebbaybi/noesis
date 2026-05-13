from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResearchSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    url: str | None = None
    publisher: str | None = None
    source_type: Literal["article", "tweet", "thread", "report", "note", "unknown"] = "unknown"
    credibility: float = Field(default=0.5, ge=0.0, le=1.0)


class ResearchFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str = Field(min_length=1, max_length=200)
    detail: str = Field(min_length=1, max_length=500)
    stance: Literal["bullish", "bearish", "neutral", "mixed"] = "neutral"
    risk_note: str | None = None
    sources: list[ResearchSource] = Field(default_factory=list)


class ResearchBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    executive_summary: str
    findings: list[ResearchFinding] = Field(default_factory=list)
    next_questions: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    mode: Literal["local", "api", "hybrid"] = "local"

    def render_digest(self, max_findings: int = 3) -> str:
        lines = [self.executive_summary.strip()]
        for finding in self.findings[:max_findings]:
            lines.append(f"- {finding.headline}: {finding.detail}")
        return "\n".join(line for line in lines if line)


__all__ = ["ResearchBrief", "ResearchFinding", "ResearchSource"]
