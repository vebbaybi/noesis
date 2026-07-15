from __future__ import annotations


class ThumbnailPrompts:
    def build(self, title: str, tone: str = "bold") -> str:
        return f"Create a {tone} podcast thumbnail with the headline: '{title}'."
