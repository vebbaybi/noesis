from __future__ import annotations

from noesis_agent.infrastructure.config import Settings, list_runtime_profiles, load_feature_flags, settings
from noesis_agent.cognition.prompts.service import PromptConfig


def test_settings_expose_runtime_profile_and_prompt_paths() -> None:
    assert settings.runtime_profile.name in list_runtime_profiles()
    assert settings.pentagon_path.exists()
    assert settings.prompts_yaml_path.exists()
    assert isinstance(settings.openai_api_key, str)


def test_feature_flag_loader_accepts_csv_and_json_styles() -> None:
    csv_flags = load_feature_flags("enable_prompt_debugging=true,!enable_voice_training")
    json_flags = load_feature_flags({"enable_local_brain": False, "enable_finance_guardrails": True})

    assert csv_flags.enable_prompt_debugging is True
    assert csv_flags.enable_voice_training is False
    assert json_flags.enable_local_brain is False
    assert json_flags.enable_finance_guardrails is True


def test_settings_validation_reports_disabled_external_requirements() -> None:
    config = Settings(
        NOESIS_ENV="development",
        NOESIS_ENABLE_DISCORD=True,
        DISCORD_BOT_TOKEN="",
        NOESIS_ENABLE_X=True,
        X_API_KEY="",
        X_API_SECRET="",
        X_ACCESS_TOKEN="",
        X_ACCESS_TOKEN_SECRET="",
    )

    issues = config.validate_environment()

    assert any(issue.key == "DISCORD_BOT_TOKEN" and issue.severity == "warning" for issue in issues)
    assert any(issue.key == "X_API_*" and issue.severity == "warning" for issue in issues)


def test_prompt_config_uses_pentagon_and_yaml_overlay() -> None:
    config = PromptConfig()
    config.reload()

    prompt = config.build_host_reply_prompt(
        context="Need a sharp answer on NFT liquidity and treasury risk.",
        topic="NFT liquidity",
        length="short",
    )

    assert config.get_name() == "NOESIS"
    assert "Use the NOESIS local brain first" in prompt
    assert "Financial discussion must stay analytical" in prompt
    assert "host_reply" in config.list_templates()
