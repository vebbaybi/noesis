from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from noesis_agent.infrastructure.config.defaults import (
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
from noesis_agent.infrastructure.config.feature_flags import FeatureFlags, load_feature_flags
from noesis_agent.infrastructure.config.profiles import RuntimeProfile, get_runtime_profile


PROJECT_ROOT = Path(__file__).resolve().parents[4]


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
    intelligence_pipeline_enabled: bool = Field(default=True, alias="NOESIS_INTELLIGENCE_PIPELINE_ENABLED")
    local_llm_enabled: bool = Field(default=True, alias="NOESIS_LOCAL_LLM_ENABLED")
    local_llm_model: str = Field(default="openai/local-model", alias="NOESIS_LOCAL_LLM_MODEL")
    local_llm_base_url: str = Field(default="http://127.0.0.1:11434/v1", alias="NOESIS_LOCAL_LLM_BASE_URL")
    external_llm_enabled: bool = Field(default=False, alias="NOESIS_EXTERNAL_LLM_ENABLED")
    external_llm_model: str = Field(default="openai/gpt-4o-mini", alias="NOESIS_EXTERNAL_LLM_MODEL")
    llm_max_attempts: int = Field(default=2, ge=1, le=5, alias="NOESIS_LLM_MAX_ATTEMPTS")
    llm_concurrency: int = Field(default=8, ge=1, le=64, alias="NOESIS_LLM_CONCURRENCY")
    llm_circuit_cooldown_seconds: float = Field(default=30.0, ge=1.0, le=600.0,
                                                 alias="NOESIS_LLM_CIRCUIT_COOLDOWN_SECONDS")

    rag_enabled: bool = Field(default=False, alias="NOESIS_RAG_ENABLED")
    qdrant_url: str = Field(default="http://127.0.0.1:6333", alias="NOESIS_QDRANT_URL")
    qdrant_collection: str = Field(default="noesis_memory_v1", alias="NOESIS_QDRANT_COLLECTION")
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", alias="NOESIS_EMBEDDING_MODEL")
    embedding_dimension: int = Field(default=384, ge=32, le=8192, alias="NOESIS_EMBEDDING_DIMENSION")
    embedding_concurrency: int = Field(default=2, ge=1, le=16, alias="NOESIS_EMBEDDING_CONCURRENCY")

    moderation_stage_two_enabled: bool = Field(default=False, alias="NOESIS_MODERATION_STAGE_TWO_ENABLED")
    moderation_fail_closed: bool = Field(default=False, alias="NOESIS_MODERATION_FAIL_CLOSED")
    moderation_device: str = Field(default="cpu", alias="NOESIS_MODERATION_DEVICE")

    redis_enabled: bool = Field(default=False, alias="NOESIS_REDIS_ENABLED")
    redis_url: str = Field(default="redis://127.0.0.1:6379/0", alias="NOESIS_REDIS_URL")

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
    memory_observation_mode: Literal["mentions_only", "observe_authorized", "observe_and_remember", "observe_and_moderate", "full_authorized_assistance", "disabled"] = Field(
        default="mentions_only", alias="NOESIS_MEMORY_OBSERVATION_MODE")
    discord_observation_overrides_raw: str = Field(default="{}", alias="NOESIS_DISCORD_OBSERVATION_OVERRIDES")
    ambient_response_enabled: bool = Field(default=False, alias="NOESIS_AMBIENT_RESPONSE_ENABLED")
    moderation_analysis_enabled: bool = Field(default=True, alias="NOESIS_MODERATION_ANALYSIS_ENABLED")
    moderation_human_review_required: bool = Field(default=True, alias="NOESIS_MODERATION_HUMAN_REVIEW_REQUIRED")
    ambient_response_cooldown_seconds: int = Field(default=60, ge=0, le=86400, alias="NOESIS_AMBIENT_RESPONSE_COOLDOWN_SECONDS")
    autonomous_memory_enabled: bool = Field(default=True, alias="NOESIS_AUTONOMOUS_MEMORY_ENABLED")
    memory_candidate_extraction_enabled: bool = Field(default=True, alias="NOESIS_MEMORY_CANDIDATE_EXTRACTION_ENABLED")
    memory_max_candidates_per_event: int = Field(default=4, ge=1, le=20, alias="NOESIS_MEMORY_MAX_CANDIDATES_PER_EVENT")
    memory_working_limit: int = Field(default=50, ge=5, le=1000, alias="NOESIS_MEMORY_WORKING_LIMIT")
    memory_persistent_threshold: float = Field(default=.7, ge=0, le=1, alias="NOESIS_MEMORY_PERSISTENT_THRESHOLD")
    memory_actionability_threshold: float = Field(default=.7, ge=0, le=1, alias="NOESIS_MEMORY_ACTIONABILITY_THRESHOLD")
    memory_importance_threshold: float = Field(default=.7, ge=0, le=1, alias="NOESIS_MEMORY_IMPORTANCE_THRESHOLD")
    memory_confidence_threshold: float = Field(default=.7, ge=0, le=1, alias="NOESIS_MEMORY_CONFIDENCE_THRESHOLD")
    memory_sensitivity_rejection_threshold: float = Field(default=.5, ge=0, le=1, alias="NOESIS_MEMORY_SENSITIVITY_REJECTION_THRESHOLD")
    memory_default_retention_class: Literal["working", "project", "long_term"] = Field(default="project", alias="NOESIS_MEMORY_DEFAULT_RETENTION_CLASS")
    memory_max_retrieval_count: int = Field(default=5, ge=1, le=20, alias="NOESIS_MEMORY_MAX_RETRIEVAL_COUNT")
    memory_queue_size: int = Field(default=128, ge=1, le=4096, alias="NOESIS_MEMORY_QUEUE_SIZE")
    memory_worker_count: int = Field(default=2, ge=1, le=8, alias="NOESIS_MEMORY_WORKER_COUNT")
    memory_write_timeout_seconds: float = Field(default=3, ge=.1, le=30, alias="NOESIS_MEMORY_WRITE_TIMEOUT_SECONDS")
    memory_retrieval_timeout_seconds: float = Field(default=3, ge=.1, le=30, alias="NOESIS_MEMORY_RETRIEVAL_TIMEOUT_SECONDS")
    memory_operator_preview_limit: int = Field(default=6, ge=1, le=20, alias="NOESIS_MEMORY_OPERATOR_PREVIEW_LIMIT")
    memory_candidate_hold_seconds: int = Field(default=300, ge=0, le=86400, alias="NOESIS_MEMORY_CANDIDATE_HOLD_SECONDS")
    memory_community_vocabulary_decay_days: int = Field(default=90, ge=1, le=3650, alias="NOESIS_MEMORY_COMMUNITY_VOCABULARY_DECAY_DAYS")
    memory_task_expiration_days: int = Field(default=365, ge=1, le=3650, alias="NOESIS_MEMORY_TASK_EXPIRATION_DAYS")
    memory_contradiction_policy: Literal["supersede", "hold_for_review"] = Field(default="supersede", alias="NOESIS_MEMORY_CONTRADICTION_POLICY")
    memory_audit_retention_days: int = Field(default=90, ge=1, le=3650, alias="NOESIS_MEMORY_AUDIT_RETENTION_DAYS")
    memory_diagnostic_mode: bool = Field(default=False, alias="NOESIS_MEMORY_DIAGNOSTIC_MODE")

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
        try:
            overrides = json.loads(self.discord_observation_overrides_raw or "{}")
            valid_modes = {"mentions_only", "observe_authorized", "observe_and_remember",
                           "observe_and_moderate", "full_authorized_assistance", "disabled"}
            if not isinstance(overrides, dict) or any(mode not in valid_modes for mode in overrides.values()):
                raise ValueError
        except (ValueError, TypeError, json.JSONDecodeError):
            issues.append(SettingsIssue(
                key="NOESIS_DISCORD_OBSERVATION_OVERRIDES", severity="error",
                message="Discord observation overrides must be a JSON object whose values are valid observation modes.",
            ))

        if self.memory_observation_mode in {"observe_and_remember", "full_authorized_assistance"} and not self.autonomous_memory_enabled:
            issues.append(SettingsIssue(
                key="NOESIS_AUTONOMOUS_MEMORY_ENABLED", severity="error",
                message="The selected observation mode requires autonomous memory to be enabled.",
            ))
        if self.ambient_response_enabled and self.memory_observation_mode != "full_authorized_assistance":
            issues.append(SettingsIssue(
                key="NOESIS_AMBIENT_RESPONSE_ENABLED", severity="error",
                message="Ambient responses require full_authorized_assistance observation mode.",
            ))

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

        if self.external_llm_enabled and not self.openai_api_key:
            issues.append(SettingsIssue(
                key="OPENAI_API_KEY", severity="error" if self.env == "production" else "warning",
                message="External LLM fallback is enabled but OPENAI_API_KEY is missing.",
            ))
        if self.rag_enabled and not self.qdrant_url:
            issues.append(SettingsIssue(key="NOESIS_QDRANT_URL", severity="error",
                                        message="RAG is enabled but Qdrant URL is empty."))
        if self.redis_enabled and not self.redis_url:
            issues.append(SettingsIssue(key="NOESIS_REDIS_URL", severity="error",
                                        message="Redis is enabled but Redis URL is empty."))

        if self.enable_elka and not self.elka_base_url:
            issues.append(
                SettingsIssue(
                    key="ELKA_BASE_URL",
                    severity="error",
                    message="ELKA is enabled but ELKA_BASE_URL is missing.",
                )
            )

        return issues

    def discord_observation_mode_for(self, *, guild_id: object = None,
                                     channel_id: object = None, thread_id: object = None) -> str:
        try:
            overrides = json.loads(self.discord_observation_overrides_raw or "{}")
        except (ValueError, TypeError, json.JSONDecodeError):
            return self.memory_observation_mode
        keys = [f"thread:{thread_id}", f"channel:{channel_id}", f"guild:{guild_id}"]
        return next((str(overrides[key]) for key in keys if key in overrides), self.memory_observation_mode)

    def startup_errors(self) -> list[SettingsIssue]:
        return [issue for issue in self.validate_environment() if issue.severity == "error"]

settings = Settings()


def get_settings() -> Settings:
    return settings
