from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Optional

DEFAULT_ENV = "development"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_NAME = "NOESIS"
DEFAULT_COMPANY_NAME = "The 1807"
DEFAULT_DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_REALTIME_MODEL = "gpt-realtime"
DEFAULT_FALLBACK_MODEL = "gpt-3.5-turbo"
DEFAULT_PRIMARY_PLATFORM = "x"
DEFAULT_DATA_DIR = Path(".noesis_data")
DEFAULT_PENTAGON_FILENAME = "pentagon.json"
DEFAULT_PROMPTS_YAML_FILENAME = "prompts.yaml"

DEFAULT_LOGGING = MappingProxyType(
    {
        "level": "INFO",
        "json_format": False,
        "alerts_enabled": False,
        "alert_webhook_url": None,
        "rate_limit": (10, 60),
        "sentry_dsn": None,
    }
)

DEFAULT_WEB3 = MappingProxyType(
    {
        "default_chain_id": 1,
        "rpc_urls": {1: "https://eth.llamarpc.com"},
        "fallback_rpc_urls": {},
        "wallet_address": None,
        "private_key": None,
        "gas_limit_multiplier": 1.2,
    }
)

DEFAULT_AUDIO = MappingProxyType(
    {
        "sample_rate": 16000,
        "channels": 1,
        "chunk_size": 1024,
        "vad_sensitivity": 2,
        "tts_voice": "alloy",
        "tts_model": "tts-1",
        "tts_speed": 1.0,
    }
)

DEFAULT_MEMORY = MappingProxyType(
    {
        "embedding_model": "text-embedding-3-small",
        "vector_store_path": Path("data/vector_store"),
        "similarity_threshold": 0.75,
        "max_working_memory_entries": 20,
        "episodic_retention_days": 30,
    }
)

DEFAULT_SESSION = MappingProxyType(
    {
        "max_duration_minutes": 240,
        "max_transcript_entries": 1000,
        "cleanup_interval_seconds": 3600,
        "default_room_capacity": 10,
    }
)

DEFAULT_PLATFORM_OVERRIDES = MappingProxyType(
    {
        "x_max_post_length": 280,
        "x_max_thread_posts": 25,
        "discord_max_message_length": 2000,
    }
)

DEFAULT_FEATURE_FLAGS = MappingProxyType(
    {
        "enable_pentagon_prompts": True,
        "enable_prompt_yaml_overlays": True,
        "enable_runtime_profiles": True,
        "enable_local_brain": True,
        "enable_local_nlp": True,
        "enable_hybrid_retrieval": True,
        "enable_adaptive_policy": True,
        "enable_finance_guardrails": True,
        "enable_humor_engine": True,
        "enable_voice_profiles": True,
        "enable_voice_training": True,
        "enable_web3_responses": True,
        "enable_audience_awareness": False,
        "enable_dynamic_prompt_reload": True,
        "enable_experimental_tts": False,
        "enable_local_fallback": True,
        "humor_rollout_percent": 100,
        "enable_prompt_debugging": False,
    }
)

DEFAULT_INLINE_TEMPLATES = MappingProxyType(
    {
        "host_opening": (
            "{identity}\nOpen the room cleanly, set expectations, and frame the topic.\n"
            "Tone: {tone}\n{length}\nTopic: {topic}\nContext: {context}"
        ),
        "host_transition": (
            "{identity}\nBridge smoothly from one topic to the next without losing momentum.\n"
            "Tone: {tone}\n{length}\nFrom: {from_topic}\nTo: {to_topic}\nContext: {context}"
        ),
        "guest_reply": (
            "{identity}\nAnswer as a sharp guest or co-host with strong domain clarity.\n"
            "Tone: {tone}\n{length}\nTopic: {topic}\nQuestion: {context}\nExpertise: {expertise}"
        ),
        "moderation_redirect": (
            "{identity}\nRedirect the room firmly but smoothly.\n"
            "Tone: {tone}\nBehavior: {offending_behavior}\nUrgency: {urgency}\nContext: {context}"
        ),
        "research_scan": (
            "{identity}\nResearch this topic with concise, source-aware structure.\n"
            "Tone: {tone}\nDepth: {depth}\nTopic: {topic}"
        ),
        "show_notes": (
            "{identity}\nTurn the session into structured show notes and post-production material.\n"
            "Tone: {tone}\nSession title: {session_title}\nContext: {context}"
        ),
    }
)

DEFAULT_PROFILE_DEFINITIONS = MappingProxyType(
    {
        "development": {
            "log_level": "DEBUG",
            "default_model": "gpt-4.1-mini",
            "realtime_model": "gpt-realtime",
            "host_temperature": 0.72,
            "max_reply_tokens": 420,
            "x_poll_interval_seconds": 45,
            "research_max_results": 5,
            "voice_speed": 1.0,
            "dry_run_external_writes": True,
        },
        "staging": {
            "log_level": "INFO",
            "default_model": "gpt-4.1-mini",
            "realtime_model": "gpt-realtime",
            "host_temperature": 0.68,
            "max_reply_tokens": 360,
            "x_poll_interval_seconds": 30,
            "research_max_results": 6,
            "voice_speed": 1.0,
            "dry_run_external_writes": False,
        },
        "production": {
            "log_level": "WARNING",
            "default_model": "gpt-4.1-mini",
            "realtime_model": "gpt-realtime",
            "host_temperature": 0.64,
            "max_reply_tokens": 320,
            "x_poll_interval_seconds": 20,
            "research_max_results": 7,
            "voice_speed": 0.98,
            "dry_run_external_writes": False,
        },
    }
)

DEFAULT_PENTAGON_FALLBACK = {
    "identity": {
        "name": DEFAULT_NAME,
        "company": DEFAULT_COMPANY_NAME,
        "base_persona": (
            "You are NOESIS, an advanced live media host and operator. "
            "Be sharp, grounded, witty, and useful."
        ),
    },
    "tones": {
        "professional_host": "clear, polished, composed, and confident",
        "analytical": "measured, evidence-first, direct, and technically sharp",
        "roast_light": "playful, funny, and brief without being cruel",
    },
    "lengths": {
        "short": "Reply in 1-3 sentences.",
        "medium": "Reply in 3-6 sentences.",
        "long": "Reply in up to 10 sentences.",
        "thread": "Format as short thread-ready segments.",
    },
    "personalities": {
        "default": "Balanced NOESIS with crisp live-room instincts.",
    },
    "prompt_templates": {
        "planner": {
            "system": (
                "{identity}\nCreate a structured live-session plan as clean JSON.\n"
                "Tone: {tone}\nAudience: {target_audience}\n{length}"
            )
        },
        "host_reply": {
            "system": (
                "{identity}\nWrite one concise live host reply.\n"
                "Personality: {personality}\nTone: {tone}\n{length}\nContext: {context}"
            )
        },
        "session_summary": {
            "system": (
                "{identity}\nSummarize the finished session as structured JSON with key moments, "
                "thread-ready recap content, and next ideas.\nTone: {tone}"
            )
        },
        "session_announcement": {
            "system": (
                "{identity}\nWrite an engaging announcement for an upcoming NOESIS session.\n"
                "Tone: {tone}\n{length}"
            )
        },
        "nft_hashtags": {
            "system": (
                "{identity}\nGenerate only concise, high-signal crypto/NFT/Web3 hashtags.\n"
                "Context: {context}\nTone: {tone}"
            )
        },
        "light_roast": {
            "system": (
                "{identity}\nLightly roast '{target}' in one or two funny, non-toxic lines.\nTone: {tone}"
            )
        },
        "call_out_shill": {
            "system": (
                "{identity}\nCall out obvious shilling in one crisp, funny line.\nTone: {tone}"
            )
        },
        "call_out_rookies": {
            "system": (
                "{identity}\nWelcome '{target}' to the space while lightly roasting the rookie moment.\nTone: {tone}"
            )
        },
    },
    "tone_selection_rules": [
        {"if": "context contains 'pump' or 'moon' or 'send it'", "then": "exuberant_web3"},
        {"if": "context contains 'scam' or 'rug' or 'dev sold'", "then": "skeptical"},
        {"else": "professional_host"},
    ],
}


def default_config_dir() -> Path:
    return Path(__file__).resolve().parent


def deep_merge_dicts(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(dict(base))
    for key, value in overlay.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, Mapping):
            merged[key] = deep_merge_dicts(existing, value)
        else:
            merged[key] = deepcopy(value)
    return merged


__all__ = [
    "DEFAULT_AUDIO",
    "DEFAULT_COMPANY_NAME",
    "DEFAULT_DATA_DIR",
    "DEFAULT_DEFAULT_MODEL",
    "DEFAULT_ENV",
    "DEFAULT_FALLBACK_MODEL",
    "DEFAULT_FEATURE_FLAGS",
    "DEFAULT_HOST",
    "DEFAULT_INLINE_TEMPLATES",
    "DEFAULT_LOG_LEVEL",
    "DEFAULT_LOGGING",
    "DEFAULT_MEMORY",
    "DEFAULT_NAME",
    "DEFAULT_PENTAGON_FALLBACK",
    "DEFAULT_PENTAGON_FILENAME",
    "DEFAULT_PLATFORM_OVERRIDES",
    "DEFAULT_PORT",
    "DEFAULT_PRIMARY_PLATFORM",
    "DEFAULT_PROFILE_DEFINITIONS",
    "DEFAULT_PROMPTS_YAML_FILENAME",
    "DEFAULT_REALTIME_MODEL",
    "DEFAULT_SESSION",
    "DEFAULT_WEB3",
    "deep_merge_dicts",
    "default_config_dir",
]