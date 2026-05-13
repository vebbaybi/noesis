from __future__ import annotations

from noesis_agent.core.lifecycle import ApplicationLifecycle


class NoesisAgent(ApplicationLifecycle):
    """Backward-compatible facade for the production application lifecycle."""


__all__ = ["NoesisAgent"]
