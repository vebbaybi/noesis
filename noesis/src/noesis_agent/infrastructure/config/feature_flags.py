from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from noesis_agent.infrastructure.config.defaults import DEFAULT_FEATURE_FLAGS


@dataclass(frozen=True, slots=True)
class FeatureFlags:
    enable_pentagon_prompts: bool = True
    enable_prompt_yaml_overlays: bool = True
    enable_runtime_profiles: bool = True
    enable_local_brain: bool = True
    enable_local_nlp: bool = True
    enable_hybrid_retrieval: bool = True
    enable_adaptive_policy: bool = True
    enable_finance_guardrails: bool = True
    enable_humor_engine: bool = True
    enable_voice_profiles: bool = True
    enable_voice_training: bool = True
    enable_web3_responses: bool = True
    enable_audience_awareness: bool = False
    enable_dynamic_prompt_reload: bool = True
    enable_experimental_tts: bool = False
    enable_local_fallback: bool = True
    humor_rollout_percent: int = 100
    enable_prompt_debugging: bool = False

    def as_dict(self) -> dict[str, bool | int]:
        return asdict(self)

    def is_enabled(self, name: str) -> bool:
        return bool(getattr(self, name, False))

    def get_rollout_percent(self, name: str) -> int:
        value = getattr(self, name, None)
        if isinstance(value, int):
            return value
        return 0


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "yes", "on", "enabled"}


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _parse_overrides(raw: Optional[str | dict[str, Any]]) -> dict[str, Any]:
    if raw is None:
        return {}

    if isinstance(raw, dict):
        return {k: _coerce_bool(v) if isinstance(v, (bool, str)) else _coerce_int(v) for k, v in raw.items()}

    text = str(raw).strip()
    if not text:
        return {}

    if text.startswith("{"):
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("NOESIS_FEATURE_FLAGS JSON must be an object")
        return {k: _coerce_bool(v) if isinstance(v, (bool, str)) else _coerce_int(v) for k, v in parsed.items()}

    overrides: dict[str, Any] = {}
    for item in text.split(","):
        token = item.strip()
        if not token:
            continue
        if "=" in token:
            key, value = token.split("=", 1)
            key = key.strip()
            if key.endswith("_percent") or key.endswith("_rollout"):
                overrides[key] = _coerce_int(value)
            else:
                overrides[key] = _coerce_bool(value)
            continue
        if token.startswith("!"):
            overrides[token[1:].strip()] = False
            continue
        overrides[token] = True
    return overrides


def load_feature_flags(
    raw: Optional[str | dict[str, Any]] = None,
    *,
    env: Optional[str] = None,
) -> FeatureFlags:
    env = env or os.environ.get("NOESIS_ENV", "development")
    values = dict(DEFAULT_FEATURE_FLAGS)

    overrides = _parse_overrides(raw)
    for key, value in overrides.items():
        if key in values:
            if isinstance(value, int) and isinstance(values[key], int):
                values[key] = value
            elif isinstance(value, bool) and isinstance(values[key], bool):
                values[key] = value
            else:
                values[key] = value

    if env.strip().lower() == "production":
        values["enable_prompt_debugging"] = overrides.get("enable_prompt_debugging", False)

    return FeatureFlags(**values)


__all__ = ["FeatureFlags", "load_feature_flags"]
