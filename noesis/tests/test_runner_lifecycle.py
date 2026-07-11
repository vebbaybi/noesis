from __future__ import annotations

import asyncio

from noesis_agent.config.settings import settings
from noesis_agent.core.lifecycle import ApplicationLifecycle
from noesis_agent.services.container import get_container


def test_lifecycle_startup_and_shutdown_with_external_integrations_disabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "enable_api", False)
    monkeypatch.setattr(settings, "enable_discord", False)
    monkeypatch.setattr(settings, "discord_bot_token", "")
    monkeypatch.setattr(settings, "enable_live_agent", False)
    monkeypatch.setattr(settings, "enable_x", False)
    monkeypatch.setattr(settings, "x_api_key", "")
    monkeypatch.setattr(settings, "x_api_secret", "")
    monkeypatch.setattr(settings, "x_access_token", "")
    monkeypatch.setattr(settings, "x_access_token_secret", "")
    monkeypatch.setattr(settings, "x_bearer_token", "")
    get_container.cache_clear()

    async def run_lifecycle() -> None:
        lifecycle = ApplicationLifecycle()
        await lifecycle.start()
        assert lifecycle.background_manager.tasks() == []
        await lifecycle.shutdown()

    asyncio.run(run_lifecycle())
    get_container.cache_clear()
