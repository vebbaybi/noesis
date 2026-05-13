from __future__ import annotations

import time
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from noesis_agent.config.settings import settings
from noesis_agent.services.prompts import PromptConfig, build_announcement_prompt, build_nft_hashtag_prompt
from noesis_agent.clients.openai_client import OpenAIService
from noesis_agent.utils.noesislogger import NoesisLogger, get_noesis_logger


class PlatformRegistry:
    PLATFORMS = {
        "x": {"name": "X", "max_length": 280, "threads": True, "emoji": True, "md": False},
        "discord": {"name": "Discord", "max_length": 2000, "threads": False, "emoji": True, "md": True},
    }

    @classmethod
    def get(cls, platform: str) -> Dict[str, Any]:
        return cls.PLATFORMS.get(platform.lower(), cls.PLATFORMS["x"])

    @classmethod
    def valid_platforms(cls) -> set[str]:
        return set(cls.PLATFORMS.keys())


class EmojiHelper:
    SET = {
        "announce": "📢",
        "event": "🎙️",
        "nft": "🖼️💎",
        "alpha": "🔥",
        "bullish": "🚀📈",
        "warning": "⚠️",
        "success": "✅",
    }

    @classmethod
    def pick(cls, text: str, mood: str = "neutral") -> str:
        t = text.lower()
        if any(w in t for w in ["live", "space", "session", "join", "starting"]):
            return cls.SET["event"] + " "
        if any(w in t for w in ["nft", "mint", "drop", "floor", "collection"]):
            return cls.SET["nft"] + " "
        if mood in ["bullish", "exuberant", "alpha"]:
            return cls.SET["alpha"] + " "
        if "warning" in t or "caution" in t:
            return cls.SET["warning"] + " "
        return ""


class PlatformService:
    def __init__(
        self,
        openai: Optional[OpenAIService] = None,
        logger: NoesisLogger | None = None,
        prompt_config: PromptConfig | None = None,
    ):
        self.openai = openai
        self.logger = logger or get_noesis_logger("noesis.service.platform")
        self.prompt_config = prompt_config or PromptConfig()
        self.primary = settings.primary_platform.lower() if settings.primary_platform else "x"
        self.logger.info(f"PlatformService initialized — primary = {self.primary}")

    async def format_announcement(
        self,
        content: str,
        platform: str | None = None,
        mood: str = "neutral",
        include_emoji: bool = True,
        add_hashtags: bool = True,
        nft_bias: bool = True,
        max_length: int | None = None,
        dry_run: bool = False,
    ) -> str:
        start = time.perf_counter()
        platform = (platform or self.primary).lower()
        spec = PlatformRegistry.get(platform)
        limit = max_length or spec["max_length"]

        text = content.strip()

        # LLM polish if short & LLM available
        if self.openai and self.openai.is_enabled() and 20 <= len(text) <= 180:
            try:
                tone = self.prompt_config.select_tone(text)
                sys_prompt = build_announcement_prompt(tone=tone, length="short")
                polished = await self.openai.generate_text(
                    system_prompt=sys_prompt,
                    user_prompt=text,
                    temperature=0.65,
                    max_tokens=140,
                )
                text = polished.strip()
            except Exception as e:
                self.logger.warning("Announcement polish failed → using raw", extra={"error": str(e)})

        # NFT bias / disclaimer
        lower = text.lower()
        if nft_bias or any(w in lower for w in ["nft", "mint", "drop", "floor", "crypto"]):
            if not any(p in lower for p in ["dyor", "not financial", "nfa"]):
                text += " — DYOR, NFA, markets move fast."

        # Emoji prefix
        if include_emoji and spec["emoji"]:
            prefix = EmojiHelper.pick(text, mood)
            text = prefix + text

        # Discord markdown enhancement
        if platform == "discord" and spec["md"]:
            text = f"**NOESIS • Announcement**\n\n{text}"

        # Hashtags (X only, when sensible)
        tags_added = 0
        if platform == "x" and add_hashtags and len(text) < limit - 60:
            tags = await self.generate_hashtags(text, max_count=5)
            space_left = limit - len(text) - 1
            added = []
            for tag in tags:
                if len(" " + tag) > space_left:
                    break
                added.append(tag)
                space_left -= len(" " + tag)
            if added:
                text += " " + " ".join(added)
                tags_added = len(added)

        # Final truncation
        if len(text) > limit - 3:
            text = text[: limit - 5].rsplit(" ", 1)[0] + "…"

        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        self.logger.debug(
            "Announcement formatted",
            extra={
                "platform": platform,
                "final_length": len(text),
                "tags_added": tags_added,
                "mood": mood,
                "latency_ms": latency_ms,
                "dry_run": dry_run,
            },
        )

        return text

    async def generate_hashtags(self, context: str, max_count: int = 6) -> List[str]:
        if not self.openai or not self.openai.is_enabled():
            return self._simple_hashtag_fallback(context)

        try:
            tone = self.prompt_config.select_tone(context)
            sys_prompt = build_nft_hashtag_prompt(context=context, tone=tone)
            raw = await self.openai.generate_text(
                system_prompt=sys_prompt,
                user_prompt=context[:600],
                temperature=0.78,
                max_tokens=90,
            )
            tags = [t.strip() for t in raw.split() if t.startswith("#") and len(t) >= 3]
            if tags:
                return tags[:max_count]
        except Exception as e:
            self.logger.warning("Hashtag generation failed → fallback", extra={"error": str(e)})

        return self._simple_hashtag_fallback(context)

    def _simple_hashtag_fallback(self, text: str) -> List[str]:
        base = ["#Web3", "#NFT", "#Crypto", "#NOESIS1807", "#1807"]
        lower = text.lower()
        extras = []
        if "solana" in lower: extras.append("#Solana")
        if "ethereum" in lower or "eth" in lower: extras.append("#Ethereum")
        if "bitcoin" in lower: extras.append("#Bitcoin")
        if "defi" in lower: extras.append("#DeFi")
        if "mint" in lower or "drop" in lower: extras.append("#NFTDrop")
        if "floor" in lower: extras.append("#NFTFloor")
        return (base + extras)[:8]

    def prepare_x_thread_segment(
        self,
        content: str,
        part: int,
        total: int,
        add_disclaimer_on_last: bool = True,
    ) -> str:
        segment = content.strip()
        if total > 1:
            segment += f"  ({part}/{total})"
        if add_disclaimer_on_last and part == total:
            segment += "\n\nDYOR • NFA • Crypto/NFT markets are volatile"
        return segment

    def decide_cross_post_targets(
        self,
        content_type: str = "announcement",
        override: str | None = None,
    ) -> Tuple[str, Optional[str]]:
        primary = override or self.primary
        secondary = None

        if primary == "x" and settings.enable_discord_cross_post:
            secondary = "discord"
        elif primary == "discord" and settings.enable_x_cross_post:
            secondary = "x"

        return primary, secondary


# Global singleton for legacy compatibility — prefer dependency injection
@lru_cache(maxsize=1)
def get_platform_service() -> PlatformService:
    return PlatformService()


class _PlatformServiceProxy:
    def __getattr__(self, name: str):
        return getattr(get_platform_service(), name)


platform_service = _PlatformServiceProxy()


__all__ = ["PlatformService", "get_platform_service", "platform_service"]
