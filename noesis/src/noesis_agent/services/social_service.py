from __future__ import annotations

import logging

from noesis_agent.content import build_summary_thread
from noesis_agent.models.media import SessionSummary
from noesis_agent.services.publisher_service import PublisherService

logger = logging.getLogger(__name__)


class SocialService:
    def __init__(self, publisher_service: PublisherService) -> None:
        self.publisher = publisher_service

    async def publish_summary_thread(
        self,
        summary: SessionSummary,
        dry_run: bool = True,
    ) -> list[dict]:
        posts = summary.x_thread or build_summary_thread(summary, add_finance_disclaimer=True)
        if not posts or not posts[0]:
            logger.warning("No thread content in summary")
            return []

        logger.info(f"Publishing recap thread ({len(posts)} parts)")
        return await self.publisher.publish_x_thread(
            posts=posts,
            dry_run=dry_run,
            add_nft_disclaimer=False,
        )
