from __future__ import annotations


class EmergencyRecoveryPipeline:
    def fallback(self) -> str:
        return "Switched to backup recording and notified hosts."
