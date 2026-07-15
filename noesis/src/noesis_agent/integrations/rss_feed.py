from __future__ import annotations

from pathlib import Path

from noesis_agent.shared.errors import ConfigurationError


class RSSFeedAdapter:
    def __init__(self, feed_path: Path) -> None:
        self.feed_path = Path(feed_path)

    def publish(self, title: str, description: str, audio_url: str) -> Path:
        try:
            from feedgen.feed import FeedGenerator
        except ImportError as exc:  # pragma: no cover - depends on optional media dependency
            raise ConfigurationError(
                "RSS publishing requires the `feedgen` package to be installed.",
                missing_key="feedgen",
            ) from exc

        fg = FeedGenerator()
        fg.title(title)
        fg.description(description)
        fg.link(href=audio_url)
        fe = fg.add_entry()
        fe.title(title)
        fe.enclosure(audio_url, 0, "audio/mpeg")
        self.feed_path.parent.mkdir(parents=True, exist_ok=True)
        fg.rss_file(self.feed_path)
        return self.feed_path
