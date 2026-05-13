from __future__ import annotations

from importlib import import_module

from .base import AudioCallback, PlatformAdapter

__all__ = [
    "PlatformAdapter",
    "AudioCallback",
    "DiscordSpaceAdapter",
    "build_discord_adapter_from_settings",
    "XSpaceAdapter",
    "YouTubeLiveAdapter",
    "SpotifyPodcastAdapter",
    "RSSFeedAdapter",
    "OBSAdapter",
    "WebRoomAdapter",
]


def __getattr__(name: str):
    module_map = {
        "DiscordSpaceAdapter": (".discord_space", "DiscordSpaceAdapter"),
        "build_discord_adapter_from_settings": (
            ".discord_space",
            "build_discord_adapter_from_settings",
        ),
        "XSpaceAdapter": (".x_space", "XSpaceAdapter"),
        "YouTubeLiveAdapter": (".youtube_live", "YouTubeLiveAdapter"),
        "SpotifyPodcastAdapter": (".spotify_podcast", "SpotifyPodcastAdapter"),
        "RSSFeedAdapter": (".rss_feed", "RSSFeedAdapter"),
        "OBSAdapter": (".obs_adapter", "OBSAdapter"),
        "WebRoomAdapter": (".web_room", "WebRoomAdapter"),
    }
    if name not in module_map:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = module_map[name]
    module = import_module(module_name, package=__name__)
    return getattr(module, attr_name)
