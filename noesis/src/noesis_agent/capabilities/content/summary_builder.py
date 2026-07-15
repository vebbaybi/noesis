from __future__ import annotations

from noesis_agent.capabilities.content.social_builder import build_summary_thread
from noesis_agent.capabilities.content.transcript_utils import extract_matching_lines, normalize_transcript_lines, trim_text
from noesis_agent.domain.contracts.media import SessionSummary

ALPHA_PATTERN = r"\b(alpha|btc|eth|sol|nft|token|mint|liquidity|market|yield|airdrop|floor|volume)\b"
FUNNY_PATTERN = r"\b(lol|haha|funny|meme|roast|cope|clown)\b"


def _build_follow_up_ideas(lines: list[str]) -> list[str]:
    joined = " ".join(lines).lower()
    ideas: list[str] = []
    if "nft" in joined:
        ideas.append("NFT liquidity and collector conviction check")
    if "btc" in joined or "eth" in joined or "market" in joined:
        ideas.append("Market structure and risk review")
    if "yield" in joined or "airdrop" in joined:
        ideas.append("Incentive design and sustainability breakdown")
    if not ideas:
        ideas = ["Builder spotlight session", "Macro and positioning review", "Community Q&A"]
    return ideas[:3]


def build_local_session_summary(session_id: str, title: str, transcript_text: str, plan_id: str | None = None) -> SessionSummary:
    lines = normalize_transcript_lines(transcript_text)

    if not lines:
        lines = [
            f"{title} wrapped with a clean operating recap.",
            "NOESIS retained the strongest themes for follow-up publishing.",
        ]

    key_moments = [trim_text(line) for line in lines[:3]]
    alpha_drops = extract_matching_lines(lines, ALPHA_PATTERN, limit=3)
    funny_moments = extract_matching_lines(lines, FUNNY_PATTERN, limit=2)
    next_episode_ideas = _build_follow_up_ideas(lines)

    discord_recap = " ".join(key_moments[:2]).strip() or f"Session complete for {title}. Summary is ready."

    summary = SessionSummary(
        session_id=session_id,
        plan_id=plan_id,
        headline=f"{title} recap",
        key_moments=key_moments,
        alpha_drops=alpha_drops,
        funny_moments=funny_moments,
        discord_recap=trim_text(discord_recap, 360),
        twitter_spaces_recap=trim_text(" | ".join(key_moments[:2]), 280) if key_moments else None,
        next_episode_ideas=next_episode_ideas,
    )
    summary.x_thread = build_summary_thread(summary, add_finance_disclaimer=True)
    return summary


__all__ = ["build_local_session_summary"]
