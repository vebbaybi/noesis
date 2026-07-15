from __future__ import annotations

from noesis_agent.capabilities.content.transcript_utils import trim_text
from noesis_agent.domain.contracts.media import SessionSummary


def build_summary_thread(summary: SessionSummary, *, add_finance_disclaimer: bool = False) -> list[str]:
    posts: list[str] = []

    headline = trim_text(summary.headline, 240)
    if headline:
        posts.append(headline)

    if summary.key_moments:
        posts.append(trim_text("Key moments: " + " | ".join(summary.key_moments[:3]), 260))

    if summary.alpha_drops:
        posts.append(trim_text("Signal: " + " | ".join(summary.alpha_drops[:2]), 260))

    if summary.funny_moments:
        posts.append(trim_text("Lighter moment: " + summary.funny_moments[0], 260))

    if summary.next_episode_ideas:
        posts.append(trim_text("Next up: " + " | ".join(summary.next_episode_ideas[:2]), 240))

    filtered_posts = [post for post in posts if post.strip()]
    if add_finance_disclaimer and any(
        keyword in " ".join(filtered_posts).lower() for keyword in ("btc", "eth", "token", "crypto", "nft", "market")
    ):
        filtered_posts.append("DYOR. This recap is commentary, not financial advice.")

    return filtered_posts


__all__ = ["build_summary_thread"]
