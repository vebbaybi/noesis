from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import noesis_agent

from noesis_agent.infrastructure.config.settings import PROJECT_ROOT, settings


COGNITION_BUILD_ID = "live-cognition-reality-fix-001"


def _git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True,
            timeout=10, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        value = result.stdout.strip()
        return value or None
    except (OSError, subprocess.SubprocessError):
        return None


def runtime_identity() -> dict[str, object]:
    env_path = PROJECT_ROOT / ".env"
    database_path = settings.data_dir / "memory" / "noesis_memory.sqlite3"
    return {
        "cognition_build_id": COGNITION_BUILD_ID,
        "git_commit": _git("rev-parse", "--short", "HEAD"),
        "git_branch": _git("branch", "--show-current"),
        "source_file_path": str(Path(noesis_agent.__file__).resolve()),
        "python_executable": str(Path(sys.executable).resolve()),
        "virtualenv_path": os.environ.get("VIRTUAL_ENV") or
                           (str(Path(sys.prefix).resolve()) if sys.prefix != sys.base_prefix else None),
        "env_file_path": str(env_path.resolve()),
        "env_file_exists": env_path.is_file(),
        "runtime_profile": settings.runtime_profile.name,
        "memory_database_path": str(database_path.resolve()),
        "observation_mode": settings.memory_observation_mode,
        "discord_enabled": settings.enable_discord,
        "live_mention_send_enabled": settings.enable_live_mention_send,
        "discord_mention_send_enabled": settings.enable_discord_mention_send,
        "recent_context_capture_enabled": settings.memory_observation_mode != "disabled",
        "memory_hygiene_enabled": True,
        "moderation_policy_mode": "human_review" if settings.moderation_human_review_required else "advisory",
    }


__all__ = ["COGNITION_BUILD_ID", "runtime_identity"]
