from __future__ import annotations


class CohostSyncPipeline:
    def sync(self, cohosts: list[str]) -> list[str]:
        return list(dict.fromkeys(cohosts))
