from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from noesis_agent.config.defaults import (
    DEFAULT_AUDIO,
    DEFAULT_LOGGING,
    DEFAULT_MEMORY,
    DEFAULT_PROFILE_DEFINITIONS,
    DEFAULT_SESSION,
    DEFAULT_WEB3,
)


@dataclass(frozen=True, slots=True)
class RuntimeProfile:
    name: str
    log_level: str = "INFO"
    default_model: str = "gpt-4.1-mini"
    realtime_model: str = "gpt-realtime"
    fallback_model: str = "gpt-3.5-turbo"
    host_temperature: float = 0.68
    max_reply_tokens: int = 360
    x_poll_interval_seconds: int = 30
    research_max_results: int = 6
    voice_speed: float = 1.0
    dry_run_external_writes: bool = False

    logging_overrides: dict[str, Any] = field(default_factory=dict)
    web3_overrides: dict[str, Any] = field(default_factory=dict)
    audio_overrides: dict[str, Any] = field(default_factory=dict)
    memory_overrides: dict[str, Any] = field(default_factory=dict)
    session_overrides: dict[str, Any] = field(default_factory=dict)

    def apply_to_settings(self, settings: Any) -> None:
        for field_name in [
            "log_level",
            "default_model",
            "realtime_model",
            "fallback_model",
            "host_temperature",
            "max_reply_tokens",
            "x_poll_interval_seconds",
            "research_max_results",
            "voice_speed",
            "dry_run_external_writes",
        ]:
            if hasattr(settings, field_name):
                setattr(settings, field_name, getattr(self, field_name))

        if self.logging_overrides and hasattr(settings, "logging"):
            for k, v in self.logging_overrides.items():
                if hasattr(settings.logging, k):
                    setattr(settings.logging, k, v)

        if self.web3_overrides and hasattr(settings, "web3"):
            for k, v in self.web3_overrides.items():
                if hasattr(settings.web3, k):
                    setattr(settings.web3, k, v)

        if self.audio_overrides and hasattr(settings, "audio"):
            for k, v in self.audio_overrides.items():
                if hasattr(settings.audio, k):
                    setattr(settings.audio, k, v)

        if self.memory_overrides and hasattr(settings, "memory"):
            for k, v in self.memory_overrides.items():
                if hasattr(settings.memory, k):
                    setattr(settings.memory, k, v)

        if self.session_overrides and hasattr(settings, "session"):
            for k, v in self.session_overrides.items():
                if hasattr(settings.session, k):
                    setattr(settings.session, k, v)


ENRICHED_PROFILE_DEFINITIONS = {
    "development": {
        **DEFAULT_PROFILE_DEFINITIONS["development"],
        "logging_overrides": {"level": "DEBUG", "json_format": False},
        "web3_overrides": {"rpc_urls": {1: "https://eth.llamarpc.com", 137: "https://polygon-rpc.com"}},
        "audio_overrides": {"tts_voice": "echo", "tts_speed": 1.1},
        "memory_overrides": {"similarity_threshold": 0.65, "episodic_retention_days": 7},
        "session_overrides": {"max_duration_minutes": 60},
    },
    "staging": {
        **DEFAULT_PROFILE_DEFINITIONS["staging"],
        "logging_overrides": {"level": "INFO", "json_format": True},
        "web3_overrides": {"rpc_urls": {1: "https://eth-mainnet.g.alchemy.com/v2/demo", 42161: "https://arb1.arbitrum.io/rpc"}},
        "audio_overrides": {"tts_voice": "alloy", "tts_speed": 1.0},
        "memory_overrides": {"similarity_threshold": 0.70, "episodic_retention_days": 14},
        "session_overrides": {"max_duration_minutes": 120},
    },
    "production": {
        **DEFAULT_PROFILE_DEFINITIONS["production"],
        "logging_overrides": {"level": "WARNING", "json_format": True, "alerts_enabled": True},
        "web3_overrides": {"default_chain_id": 1, "gas_limit_multiplier": 1.5},
        "audio_overrides": {"tts_voice": "onyx", "tts_speed": 0.98},
        "memory_overrides": {"similarity_threshold": 0.75, "episodic_retention_days": 30},
        "session_overrides": {"max_duration_minutes": 240, "default_room_capacity": 50},
    },
    "test": {
        **DEFAULT_PROFILE_DEFINITIONS["development"],
        "log_level": "DEBUG",
        "dry_run_external_writes": True,
        "logging_overrides": {"level": "DEBUG", "json_format": False},
        "web3_overrides": {},
        "audio_overrides": {},
        "memory_overrides": {"similarity_threshold": 0.65, "episodic_retention_days": 7},
        "session_overrides": {"max_duration_minutes": 60},
    },
}


def get_runtime_profile(name: Optional[str] = None) -> RuntimeProfile:
    normalized = (name or "development").strip().lower()
    if normalized not in ENRICHED_PROFILE_DEFINITIONS:
        normalized = "development"
    payload = ENRICHED_PROFILE_DEFINITIONS[normalized]
    return RuntimeProfile(name=normalized, **payload)


def list_runtime_profiles() -> list[str]:
    return sorted(ENRICHED_PROFILE_DEFINITIONS.keys())


__all__ = ["RuntimeProfile", "get_runtime_profile", "list_runtime_profiles"]
