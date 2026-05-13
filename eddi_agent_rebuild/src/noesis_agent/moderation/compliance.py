from __future__ import annotations


class ComplianceChecker:
    """Handles simple recording consent and region checks."""

    def __init__(self, require_consent: bool = True) -> None:
        self.require_consent = require_consent

    def is_recording_allowed(self, consent_given: bool, region: str | None = None) -> bool:
        if self.require_consent and not consent_given:
            return False
        return True
