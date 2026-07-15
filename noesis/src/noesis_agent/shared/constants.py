from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Final, Mapping, Sequence


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Platform(str, Enum):
    OPENAI = "openai"
    X = "x"
    DISCORD = "discord"


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    requests_per_minute: int | None = None
    tokens_per_minute: int | None = None
    messages_per_second: int | None = None
    webhooks_per_second: int | None = None
    posts_per_hour: int | None = None
    posts_per_day: int | None = None


@dataclass(frozen=True, slots=True)
class RetryPolicyDefaults:
    max_retries: int
    base_delay_seconds: float
    max_delay_seconds: float
    backoff_multiplier: float
    jitter_enabled: bool


@dataclass(frozen=True, slots=True)
class PersonaProfile:
    name: str
    role: str
    traits: tuple[str, ...]
    expertise: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PlatformCapabilities:
    display_name: str
    max_content_length: int
    supports_threads: bool
    hashtag_limit: int | None = None
    emoji_support: bool = False


class SessionLimits:
    MAX_SESSION_DURATION_MINUTES: Final[int] = 240
    MAX_TRANSCRIPT_ENTRIES: Final[int] = 1000
    SESSION_CLEANUP_INTERVAL_SECONDS: Final[int] = 3600


class ContentLimits:
    MAX_X_POST_LENGTH: Final[int] = 280
    MAX_X_THREAD_POSTS: Final[int] = 25
    MAX_DISCORD_MESSAGE_LENGTH: Final[int] = 2000
    MAX_SUMMARY_POINTS: Final[int] = 10


class Timeouts:
    DEFAULT_API_TIMEOUT_SECONDS: Final[int] = 30
    OPENAI_TIMEOUT_SECONDS: Final[int] = 60
    X_TIMEOUT_SECONDS: Final[int] = 30
    DISCORD_TIMEOUT_SECONDS: Final[int] = 30


class LoggingDefaults:
    ENVIRONMENT_LOG_LEVELS: Final[Mapping[Environment, str]] = MappingProxyType(
        {
            Environment.DEVELOPMENT: "DEBUG",
            Environment.STAGING: "INFO",
            Environment.PRODUCTION: "WARNING",
        }
    )


RATE_LIMITS: Final[Mapping[Platform, RateLimitPolicy]] = MappingProxyType(
    {
        Platform.OPENAI: RateLimitPolicy(
            requests_per_minute=3500,
            tokens_per_minute=90000,
        ),
        Platform.X: RateLimitPolicy(
            posts_per_hour=300,
            posts_per_day=2400,
        ),
        Platform.DISCORD: RateLimitPolicy(
            messages_per_second=5,
            webhooks_per_second=30,
        ),
    }
)

DEFAULT_RETRY_POLICY: Final[RetryPolicyDefaults] = RetryPolicyDefaults(
    max_retries=3,
    base_delay_seconds=1.0,
    max_delay_seconds=30.0,
    backoff_multiplier=2.0,
    jitter_enabled=True,
)

NOESIS_PERSONA: Final[PersonaProfile] = PersonaProfile(
    name="NOESIS",
    role="AI Host",
    traits=("knowledgeable", "enthusiastic", "helpful", "professional"),
    expertise=("Web3", "blockchain", "DeFi", "NFTs", "DAO"),
)

PLATFORM_CAPABILITIES: Final[Mapping[Platform, PlatformCapabilities]] = MappingProxyType(
    {
        Platform.X: PlatformCapabilities(
            display_name="X",
            max_content_length=ContentLimits.MAX_X_POST_LENGTH,
            supports_threads=True,
            hashtag_limit=5,
        ),
        Platform.DISCORD: PlatformCapabilities(
            display_name="Discord",
            max_content_length=ContentLimits.MAX_DISCORD_MESSAGE_LENGTH,
            supports_threads=False,
            emoji_support=True,
        ),
        Platform.OPENAI: PlatformCapabilities(
            display_name="OpenAI",
            max_content_length=0,
            supports_threads=False,
        ),
    }
)

SUPPORTED_PLATFORMS: Final[Sequence[Platform]] = tuple(PLATFORM_CAPABILITIES.keys())


def get_platform_capabilities(platform: Platform) -> PlatformCapabilities:
    return PLATFORM_CAPABILITIES[platform]


def get_rate_limits(platform: Platform) -> RateLimitPolicy:
    return RATE_LIMITS[platform]


__all__ = [
    "ContentLimits",
    "DEFAULT_RETRY_POLICY",
    "NOESIS_PERSONA",
    "Environment",
    "LoggingDefaults",
    "PLATFORM_CAPABILITIES",
    "Platform",
    "PlatformCapabilities",
    "PersonaProfile",
    "RATE_LIMITS",
    "RateLimitPolicy",
    "RetryPolicyDefaults",
    "SessionLimits",
    "SUPPORTED_PLATFORMS",
    "Timeouts",
    "get_platform_capabilities",
    "get_rate_limits",
]
