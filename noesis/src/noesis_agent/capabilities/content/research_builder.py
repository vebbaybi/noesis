from __future__ import annotations

import re

from noesis_agent.capabilities.content.transcript_utils import normalize_transcript_lines, trim_text
from noesis_agent.domain.entities.knowledge import ResearchBrief, ResearchFinding, ResearchSource


def _infer_stance(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ("bear", "risk", "downside", "unwind", "weak")):
        return "bearish"
    if any(token in lowered for token in ("bull", "strength", "breakout", "momentum", "bid")):
        return "bullish"
    if any(token in lowered for token in ("mixed", "two-sided", "unclear", "chop")):
        return "mixed"
    return "neutral"


def build_local_research_brief(query: str, raw_text: str = "", *, mode: str = "local") -> ResearchBrief:
    lines = normalize_transcript_lines(raw_text)
    findings: list[ResearchFinding] = []

    for line in lines[:4]:
        findings.append(
            ResearchFinding(
                headline=trim_text(query, 120),
                detail=trim_text(re.sub(r"^[\-\*\d.\s]+", "", line), 280),
                stance=_infer_stance(line),
                risk_note="Verify claims against primary sources before live delivery.",
                sources=[ResearchSource(title="Local synthesis", source_type="note", credibility=0.35)],
            )
        )

    if not findings:
        findings = [
            ResearchFinding(
                headline=f"{query} overview",
                detail=f"No external feed is active, so NOESIS is using local context for {query}.",
                stance="neutral",
                risk_note="Treat this as a structured offline brief.",
                sources=[ResearchSource(title="Offline NOESIS context", source_type="note", credibility=0.25)],
            )
        ]

    summary = trim_text(
        f"Brief on {query}: " + " ".join(finding.detail for finding in findings[:2]),
        260,
    )
    next_questions = [
        f"What invalidates the current thesis on {query}?",
        f"Which on-chain or market signals matter most for {query} next?",
        f"What is the highest-risk assumption in the current narrative around {query}?",
    ]
    return ResearchBrief(
        query=query,
        executive_summary=summary,
        findings=findings,
        next_questions=next_questions,
        mode="hybrid" if raw_text.strip() else mode,
    )


def render_research_digest(brief: ResearchBrief, *, max_findings: int = 3) -> str:
    lines = [brief.executive_summary]
    for finding in brief.findings[:max_findings]:
        lines.append(f"- {finding.detail}")
    return "\n".join(line for line in lines if line.strip())


__all__ = ["build_local_research_brief", "render_research_digest"]
