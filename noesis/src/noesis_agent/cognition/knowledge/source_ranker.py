from __future__ import annotations

import tldextract


class SourceRanker:
    """Simple heuristic source scoring based on domain reputation."""

    TRUSTED = {"reuters.com", "apnews.com", "bbc.co.uk", "nytimes.com", "theverge.com"}

    def score(self, url: str) -> float:
        ext = tldextract.extract(url)
        domain = ".".join(part for part in [ext.domain, ext.suffix] if part)
        if domain in self.TRUSTED:
            return 1.0
        if domain.endswith(".gov") or domain.endswith(".edu"):
            return 0.9
        if domain.endswith(".blog"):
            return 0.4
        return 0.6
