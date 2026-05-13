from __future__ import annotations

import asyncio
import httpx

from noesis_agent.clients.openai_client import OpenAIService
from noesis_agent.utils.noesislogger import NoesisLogger


class Researcher:
    """Lightweight web researcher combining DuckDuckGo instant answers with LLM summarization."""

    def __init__(self, openai: OpenAIService | None = None) -> None:
        self.client = httpx.AsyncClient(timeout=8.0, follow_redirects=True)
        self.openai = openai
        self.logger = NoesisLogger("noesis.knowledge.researcher").logger

    async def search(self, query: str, max_results: int = 5) -> list[dict]:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_redirect": 1, "no_html": 1}
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        topics = data.get("RelatedTopics", [])[:max_results]
        results = []
        for t in topics:
            if "Text" in t:
                results.append({"title": t.get("Text"), "url": t.get("FirstURL")})
        if data.get("AbstractText"):
            results.insert(0, {"title": data["AbstractText"], "url": data.get("AbstractURL")})
        return results[:max_results]

    async def summarize(self, query: str, max_results: int = 5) -> str:
        hits = await self.search(query, max_results=max_results)
        if not hits:
            return "No results found."

        bullet_lines = [f"- {h['title']} ({h.get('url','')})" for h in hits if h.get("title")]

        if not self.openai or not self.openai.is_enabled():
            return "\n".join(bullet_lines)

        system_prompt = (
            "You are a research summarizer. Combine the provided findings into a concise, source-aware brief."
        )
        user_prompt = f"Query: {query}\nFindings:\n" + "\n".join(bullet_lines)
        summary = await self.openai.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=240,
        )
        return summary.strip()

    async def close(self) -> None:
        await self.client.aclose()
