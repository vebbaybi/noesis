from __future__ import annotations

import asyncio
import httpx

from noesis_agent.shared.noesislogger import NoesisLogger


class NewsMonitor:
    """Polls a configurable RSS/Atom feed for fresh headlines."""

    def __init__(self, feed_url: str = "https://hnrss.org/frontpage", poll_seconds: int = 180) -> None:
        self.feed_url = feed_url
        self.poll_seconds = poll_seconds
        self.logger = NoesisLogger("noesis.knowledge.news_monitor").logger
        self._client = httpx.AsyncClient(timeout=6.0, follow_redirects=True)
        self._last_seen: set[str] = set()
        self._running = False

    async def run(self, callback) -> None:
        self._running = True
        while self._running:
            try:
                await self._poll(callback)
            except Exception as exc:  # pragma: no cover
                self.logger.warning("News monitor error", exc_info=exc)
            await asyncio.sleep(self.poll_seconds)

    async def _poll(self, callback) -> None:
        resp = await self._client.get(self.feed_url)
        resp.raise_for_status()
        text = resp.text
        items = [line for line in text.splitlines() if "<title>" in line][1:10]
        for line in items:
            title = line.replace("<title>", "").replace("</title>", "").strip()
            if title in self._last_seen:
                continue
            self._last_seen.add(title)
            await callback(title)

    async def stop(self) -> None:
        self._running = False
        await self._client.aclose()
