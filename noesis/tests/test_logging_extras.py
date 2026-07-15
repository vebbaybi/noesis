from __future__ import annotations

import ast
import logging
from pathlib import Path

from noesis_agent.infrastructure.config.settings import Settings, SettingsIssue, settings
from noesis_agent.runtime.lifecycle import ApplicationLifecycle
from noesis_agent.shared.logging import sanitize_log_extra


RESERVED = {
    "message", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName", "processName",
    "process", "name", "asctime",
}


def test_sanitize_log_extra_namespaces_every_reserved_key() -> None:
    payload = {key: f"value-{key}" for key in RESERVED}
    sanitized = sanitize_log_extra(payload)
    assert not RESERVED.intersection(sanitized)
    assert sanitized["extra_message"] == "value-message"
    logger = logging.getLogger("noesis.test.logging-extra")
    logger.warning("safe warning", extra=sanitized)


def test_environment_validation_warning_logs_without_crashing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "log_dir", tmp_path)
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "enable_discord", True)
    monkeypatch.setattr(settings, "discord_bot_token", "")
    monkeypatch.setattr(settings, "enable_x", False)
    lifecycle = ApplicationLifecycle()
    lifecycle._validate_environment()
    for handler in logging.getLogger().handlers:
        handler.flush()
    log_text = (tmp_path / "noesis_agent.log").read_text(encoding="utf-8")
    assert "Configuration validation warning" in log_text


def test_explicit_config_warning_payload_uses_safe_field_names(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "log_dir", tmp_path)
    lifecycle = ApplicationLifecycle()
    warning = SettingsIssue(key="OPTIONAL_TOKEN", severity="warning", message="Optional token is missing.")
    monkeypatch.setattr(Settings, "validate_environment", lambda self: [warning])
    lifecycle._validate_environment()


def test_literal_logging_extra_dicts_do_not_use_reserved_keys() -> None:
    violations: list[str] = []
    for path in Path("src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            extra = next((item.value for item in node.keywords if item.arg == "extra"), None)
            if not isinstance(extra, ast.Dict):
                continue
            keys = {key.value for key in extra.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)}
            for reserved in sorted(keys & RESERVED):
                violations.append(f"{path}:{node.lineno}:{reserved}")
    assert violations == []
