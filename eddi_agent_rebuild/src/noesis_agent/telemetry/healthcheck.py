from __future__ import annotations


class Healthcheck:
    def __init__(self) -> None:
        self.checks: dict[str, bool] = {}

    def set(self, name: str, ok: bool) -> None:
        self.checks[name] = ok

    def status(self) -> dict:
        return {"status": "ok" if all(self.checks.values()) else "degraded", "components": self.checks}
