"""Narrow contracts required by application use cases.

Concrete provider, persistence, and platform adapters implement these protocols;
the application layer never imports those implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class TextGenerationProvider(Protocol):
    def is_enabled(self) -> bool: ...

    async def generate_text(self, **kwargs: Any) -> str: ...


class DocumentStore(Protocol):
    def write(self, collection: str, key: str, payload: dict[str, Any]) -> Any: ...
    def read(self, collection: str, key: str) -> dict[str, Any] | None: ...
    def list(self, collection: str) -> list[dict[str, Any]]: ...


class RuntimeOptions(Protocol):
    enable_live_mention_send: bool
    enable_discord_mention_send: bool
    enable_discord: bool
    discord_bot_token: str
    enable_x: bool
    x_api_key: str
    x_api_secret: str
    x_access_token: str
    x_access_token_secret: str


@dataclass(frozen=True, slots=True)
class DisabledRuntimeOptions:
    """Safe defaults for dry-run use cases constructed outside the runtime."""

    enable_live_mention_send: bool = False
    enable_discord_mention_send: bool = False
    enable_discord: bool = False
    discord_bot_token: str = ""
    enable_x: bool = False
    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_token_secret: str = ""
