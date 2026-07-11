from __future__ import annotations

import psutil

from noesis_agent.utils.noesislogger import NoesisLogger


class SystemWatch:
    def __init__(self, cpu_warn: float = 90.0, mem_warn: float = 90.0) -> None:
        self.cpu_warn = cpu_warn
        self.mem_warn = mem_warn
        self.logger = NoesisLogger("noesis.monitors.system").logger

    def snapshot(self) -> dict:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        if cpu > self.cpu_warn or mem > self.mem_warn:
            self.logger.warning("System resources high", extra={"cpu": cpu, "mem": mem})
        return {"cpu": cpu, "mem": mem}
