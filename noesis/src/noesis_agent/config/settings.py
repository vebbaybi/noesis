from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from noesis_agent.config.defaults import (
    DEFAULT_COMPANY_NAME,
    DEFAULT_DATA_DIR,
    DEFAULT_DEFAULT_MODEL,
    DEFAULT_ENV,
    DEFAULT_HOST,
    DEFAULT_LOG_LEVEL,
    DEFAULT_NAME,
    DEFAULT_PENTAGON_FILENAME,
    DEFAULT_PORT,
    DEFAULT_PRIMARY_PLATFORM,
    DEFAULT_PROMPTS_YAML_FILENAME,
    DEFAULT_REALTIME_MODEL,
    default_config_dir,
)
from noesis_agent.config.feature_flags import FeatureFlags, load_feature_flags
from noesis_agent.config.profiles import RuntimeProfile, get_runtime_profile


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True, slots=True)
class SettingsIssue:
    key: str
    severity: Literal["warning", "error"]
    message: str


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = Field(default=DEFAULT_ENV, alias="NOESIS_ENV")
    host: str = Field(default=DEFAULT_HOST, alias="NOESIS_HOST")
    port: int = Field(default=DEFAULT_PORT, alias="NOESIS_PORT")
    log_level: str = Field(default=DEFAULT_LOG_LEVEL, alias="NOESIS_LOG_LEVEL")
    enable_api: bool = Field(default=True, alias="NOESIS_ENABLE_API")

    noesis_name: str = Field(default=DEFAULT_NAME, alias="NOESIS_NAME")
    company_name: str = Field(default=DEFAULT_COMPANY_NAME, alias="NOESIS_COMPANY_NAME")
    default_model: str = Field(default=DEFAULT_DEFAULT_MODEL, alias="NOESIS_DEFAULT_MODEL")
    realtime_model: str = Field(default=DEFAULT_REALTIME_MODEL, alias="NOESIS_REALTIME_MODEL")
    profile_name: str = Field(default="", alias="NOESIS_PROFILE")
    feature_flags_raw: str = Field(default="", alias="NOESIS_FEATURE_FLAGS")
    cognition_provider: Literal["auto", "local", "elka"] = Field(default="auto", alias="NOESIS_COGNITION_PROVIDER")
    llm_timeout_seconds: float = Field(default=30.0, ge=1.0, le=180.0, alias="NOESIS_LLM_TIMEOUT_SECONDS")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    enable_elka: bool = Field(default=False, alias="NOESIS_ENABLE_ELKA")
    elka_base_url: str = Field(default="", alias="ELKA_BASE_URL")
    elka_api_key: str = Field(default="", alias="ELKA_API_KEY")

    discord_bot_token: str = Field(default="", alias="DISCORD_BOT_TOKEN")
    discord_guild_id: int | None = Field(default=None, alias="DISCORD_GUILD_ID")
    discord_voice_channel_id: int | None = Field(default=None, alias="DISCORD_VOICE_CHANNEL_ID")
    discord_allowed_text_channel_ids: Annotated[list[int], NoDecode] = Field(
        default_factory=list,
        alias="DISCORD_ALLOWED_TEXT_CHANNEL_IDS",
    )
    enable_discord: bool = Field(default=True, alias="NOESIS_ENABLE_DISCORD")
    enable_live_mention_send: bool = Field(default=False, alias="NOESIS_ENABLE_LIVE_MENTION_SEND")
    enable_discord_mention_send: bool = Field(default=False, alias="NOESIS_ENABLE_DISCORD_MENTION_SEND")
    enable_live_agent: bool = Field(default=True, alias="NOESIS_ENABLE_LIVE_AGENT")
    auto_start_live_session: bool = Field(default=False, alias="NOESIS_AUTO_START_LIVE_SESSION")
    auto_start_live_topic: str = Field(default="Open conversation", alias="NOESIS_AUTO_START_LIVE_TOPIC")
    enable_discord_cross_post: bool = Field(default=False, alias="NOESIS_ENABLE_DISCORD_CROSS_POST")
    enable_x_cross_post: bool = Field(default=False, alias="NOESIS_ENABLE_X_CROSS_POST")

    x_api_key: str = Field(default="", alias="X_API_KEY")
    x_api_secret: str = Field(default="", alias="X_API_SECRET")
    x_access_token: str = Field(default="", alias="X_ACCESS_TOKEN")
    x_access_token_secret: str = Field(default="", alias="X_ACCESS_TOKEN_SECRET")
    x_bearer_token: str = Field(default="", alias="X_BEARER_TOKEN")
    x_handle: str = Field(default="the1807xyz", alias="X_HANDLE")
    enable_x: bool = Field(default=True, alias="NOESIS_ENABLE_X")

    primary_platform: str = Field(
        default=DEFAULT_PRIMARY_PLATFORM,
        alias="NOESIS_PRIMARY_PLATFORM",
        description="Primary publishing and formatting platform: x or discord",
    )

    data_dir: Path = Field(default=DEFAULT_DATA_DIR, alias="NOESIS_DATA_DIR")
    log_dir: Path = Field(default=Path("logs"), alias="NOESIS_LOG_DIR")

    @field_validator("env", mode="before")
    @classmethod
    def normalize_env(cls, value: object) -> str:
        env = str(value or DEFAULT_ENV).strip().lower()
        if env not in {"development", "staging", "production", "test"}:
            raise ValueError("NOESIS_ENV must be development, staging, production, or test")
        return env

    @field_validator("primary_platform", mode="before")
    @classmethod
    def validate_primary_platform(cls, value: object) -> str:
        if value is None:
            return DEFAULT_PRIMARY_PLATFORM

        v = str(value).strip().lower()
        if v not in {"x", "discord"}:
            raise ValueError("NOESIS_PRIMARY_PLATFORM must be 'x' or 'discord'")
        return v

    @field_validator("discord_guild_id", "discord_voice_channel_id", mode="before")
    @classmethod
    def parse_optional_discord_id(cls, value: object) -> int | None:
        if value is None:
            return None

        if isinstance(value, int):
            return value

        raw = str(value).strip()
        if not raw or raw == "0" or raw.upper().startswith("REPLACE_"):
            return None

        return int(raw)

    @field_validator("discord_allowed_text_channel_ids", mode="before")
    @classmethod
    def parse_discord_allowed_text_channel_ids(cls, value: object) -> list[int]:
        if value is None:
            return []

        if isinstance(value, list):
            return [int(item) for item in value]

        if isinstance(value, str):
            raw = value.strip()

            if not raw:
                return []

            if raw.upper().startswith("REPLACE_"):
                return []

            if raw == "[]":
                return []

            if raw.startswith("[") and raw.endswith("]"):
                parsed = json.loads(raw)
                if not isinstance(parsed, list):
                    raise ValueError("DISCORD_ALLOWED_TEXT_CHANNEL_IDS JSON value must be a list")
                return [int(item) for item in parsed]

            return [int(part.strip()) for part in raw.split(",") if part.strip()]

        raise ValueError(
            "Unsupported format for DISCORD_ALLOWED_TEXT_CHANNEL_IDS. "
            "Use [], a JSON list, or comma-separated ids."
        )

    @field_validator("data_dir", "log_dir", mode="after")
    @classmethod
    def resolve_runtime_path(cls, value: Path) -> Path:
        return _project_path(value)

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def config_dir(self) -> Path:
        return default_config_dir()

    @property
    def pentagon_path(self) -> Path:
        return self.config_dir / DEFAULT_PENTAGON_FILENAME

    @property
    def prompts_yaml_path(self) -> Path:
        return self.config_dir / DEFAULT_PROMPTS_YAML_FILENAME

    @property
    def runtime_profile(self) -> RuntimeProfile:
        return get_runtime_profile(self.profile_name or self.env)

    @property
    def feature_flags(self) -> FeatureFlags:
        return load_feature_flags(self.feature_flags_raw, env=self.env)

    def validate_environment(self) -> list[SettingsIssue]:
        """Return runtime configuration issues without touching external services."""
        issues: list[SettingsIssue] = []

        if self.enable_discord and not self.discord_bot_token:
            issues.append(
                SettingsIssue(
                    key="DISCORD_BOT_TOKEN",
                    severity="warning" if self.env != "production" else "error",
                    message="Discord is enabled but no bot token is configured.",
                )
            )

        if self.enable_discord_mention_send and not self.enable_live_mention_send:
            issues.append(SettingsIssue(
                key="NOESIS_ENABLE_LIVE_MENTION_SEND", severity="warning",
                message="Discord mention sending is enabled, but global live mention sending is disabled.",
            ))

        if self.auto_start_live_session:
            if not self.enable_discord:
                issues.append(
                    SettingsIssue(
                        key="NOESIS_AUTO_START_LIVE_SESSION",
                        severity="error",
                        message="Auto-starting a live Discord session requires Discord to be enabled.",
                    )
                )
            for key, value in {
                "DISCORD_BOT_TOKEN": self.discord_bot_token,
                "DISCORD_GUILD_ID": self.discord_guild_id,
                "DISCORD_VOICE_CHANNEL_ID": self.discord_voice_channel_id,
            }.items():
                if not value:
                    issues.append(
                        SettingsIssue(
                            key=key,
                            severity="error",
                            message=f"Auto-start live sessions require {key}.",
                        )
                    )

        x_credentials = [
            self.x_api_key,
            self.x_api_secret,
            self.x_access_token,
            self.x_access_token_secret,
        ]
        if self.enable_x and not all(x_credentials):
            issues.append(
                SettingsIssue(
                    key="X_API_*",
                    severity="warning" if self.env != "production" else "error",
                    message="X integration is enabled but write credentials are incomplete.",
                )
            )

        if self.cognition_provider == "elka" and not self.enable_elka:
            issues.append(
                SettingsIssue(
                    key="NOESIS_ENABLE_ELKA",
                    severity="error",
                    message="The ELKA cognition provider was selected but ELKA is not enabled.",
                )
            )

        if self.enable_elka and not self.elka_base_url:
            issues.append(
                SettingsIssue(
                    key="ELKA_BASE_URL",
                    severity="error",
                    message="ELKA is enabled but ELKA_BASE_URL is missing.",
                )
            )

        return issues

    def startup_errors(self) -> list[SettingsIssue]:
        return [issue for issue in self.validate_environment() if issue.severity == "error"]

settings = Settings()


def get_settings() -> Settings:
    return settings
