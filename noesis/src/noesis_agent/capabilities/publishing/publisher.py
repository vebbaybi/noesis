from __future__ import annotations

import logging
from typing import Any

from noesis_agent.integrations.x.client import XClient
from noesis_agent.domain.contracts.platforms import XPostRequest

logger = logging.getLogger(__name__)


class PublisherService:
    def __init__(self, x_client: XClient) -> None:
        self.x_client = x_client

    def publish_x_post(self, payload: XPostRequest) -> dict[str, Any]:
        dry_run = payload.dry_run or not self.x_client.is_enabled()
        if dry_run and not payload.dry_run:
            logger.warning("X client not enabled - dry run forced")

        result = self.x_client.post(
            text=payload.text,
            reply_to_tweet_id=payload.reply_to_tweet_id,
            dry_run=dry_run,
        )

        if "tweet_id" in result:
            logger.info("Published X post: %s -> %s...", result["tweet_id"], payload.text[:60])
        else:
            logger.warning("X publish failed or dry run: %s", result)

        return result

    async def publish_x_thread(
        self,
        posts: list[str],
        dry_run: bool = True,
        add_nft_disclaimer: bool = True,
    ) -> list[dict[str, Any]]:
        if add_nft_disclaimer and any("NFT" in post or "crypto" in post.lower() for post in posts):
            posts = posts + [
                "DYOR - not financial advice. NFT markets are volatile. Always verify on-chain."
            ]

        if not self.x_client.is_enabled():
            dry_run = True

        results = self.x_client.post_thread(posts=posts, dry_run=dry_run)

        if not dry_run:
            tweet_ids = [result.get("tweet_id") for result in results if "tweet_id" in result]
            if tweet_ids:
                logger.info("Published thread with %s posts: %s", len(tweet_ids), ", ".join(tweet_ids))

        return results
